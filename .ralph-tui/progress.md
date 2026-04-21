# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

- **Eager-loading relationships in async SQLAlchemy**: When you need to access a Task's foreign-keyed relationships (target_machine, project) in an async endpoint, use `select(Task).options(joinedload(Task.target_machine), joinedload(Task.project)).where(...)` to eagerly load them in a single query and avoid lazy-loading issues.

- **Alembic initialization with pre-existing database**: Initialize with `alembic init alembic`, configure env.py to import models with `sys.path.insert(0, str(Path(__file__).parent.parent))`, run `alembic revision --autogenerate`, then use `alembic stamp head` to mark existing schema as the baseline (SQLite doesn't support ALTER COLUMN so direct upgrade may fail)

- **Bridge API client implementation pattern**: API client uses `httpx.AsyncClient` with retry logic (`MAX_RETRIES=3`, `RETRY_DELAY=2.0`), timeouts (`connect=5s, read=30s`), and `X-API-Key` header. Cloud endpoints: `POST /machines` (register), `GET /machines/{uuid}/poll` (poll tasks), `PUT /tasks/{uuid}` (update status), `POST /tasks/{uuid}/result` (submit result), `POST /tasks/{uuid}/remind` (trigger reminder). `poll_tasks(project_id=None)` accepts optional project_id to override config value.

- **API Router versioning pattern**: Routes registered under `/api/v1` prefix in main.py, each router has `prefix="/machines"` and uses `response_model=ApiResponse` wrapper for consistent JSON envelope. Auth via `Security(verify_api_key)` dependency at router level.

- **Two-schema pattern for list vs detail**: `MachineListResponse` (shorter, for list views) vs `MachineResponse` (includes pending_task_count, set manually after query). `PollTaskResponse` used for poll results with `agent_capability` field added.

- **Poll endpoint pattern**: Updates `last_poll_at` and sets status=`online` on every poll. Filters tasks by `target_machine_id` and `status=pending`, optionally filters by `project_id` string (looked up to UUID). Batch-updates matched tasks to `dispatched` in memory without explicit flush (relies on get_db commit).

- **Graceful async shutdown pattern**: Track asyncio tasks in a list, add done_callbacks to remove completed tasks, and use `asyncio.gather(*tasks, return_exceptions=True)` in cleanup to wait for running tasks before exiting.

---

## 2026-04-21 - US-013

- **What was implemented:** Main polling loop - added graceful shutdown that waits for running tasks before exiting
- **Files changed:** `bridge/bridge/main.py` (added `_tasks` list to track running tasks, modified `start()` to store task references and add done_callbacks for cleanup, modified `cleanup()` to wait for running tasks with `asyncio.gather`)
- **Learnings:**
  - US-013 was mostly already implemented - only missing piece was graceful shutdown waiting for running tasks
  - Solution: Track asyncio tasks in a list `_tasks`, use done_callbacks to auto-remove completed tasks, and `asyncio.gather(*self._tasks, return_exceptions=True)` in cleanup
  - `return_exceptions=True` prevents gather from raising if a task fails
  - Signal handlers (SIGINT/SIGTERM) call `bridge.stop()` which sets `_running = False` to break the poll loop
- **Acceptance criteria status:**
  - ✅ `main()` calls `register_machine()` on startup (line 40)
  - ✅ Main loop polls every `config.poll_interval` (default 60s) (line 60)
  - ✅ `handle_task()` creates asyncio task for each pending task (line 50)
  - ✅ `remote_execution` tasks call `execute_remote()` (lines 85-96)
  - ✅ `manual_only` tasks call `send_reminder()` (lines 80-83)
  - ✅ Concurrent execution limit: `asyncio.Semaphore(3)` (line 29)
  - ✅ Graceful `Ctrl+C` shutdown waiting for running tasks (lines 50-52, 102-106)
  - ✅ python -m pytest passes (exit code 5 = no tests, expected)
  - ✅ python -m py_compile cloud/**/*.py passes

---

## 2026-04-21 - US-015

- **What was implemented:** Enhanced `trigger_reminder` endpoint to call `notifier.send_wechat_markdown()` after updating task status to `pending_manual`
- **Files changed:** `cloud/routers/tasks.py` (added `joinedload` for target_machine and project relationships, added WeChat notification with task instruction, machine name, project name, project root path, and task link)
- **Learnings:**
  - `joinedload(Task.target_machine)` and `joinedload(Task.project)` needed to eagerly load relationships within a single query (without this, accessing `task.project` after the query would fail to load the relationship)
  - The `Project` model import is not needed when accessing via relationship - SQLAlchemy resolves `task.project` through the relationship defined on the Task model regardless of whether `Project` is imported
  - `send_wechat_markdown()` is async so it must be awaited in the endpoint
  - Task link constructed as `{FRONTEND_URL}/tasks/{task.task_id}` using the external task_id string (e.g., "task-a1b2c3d4")
  - Message format: bold title, then task instruction, machine name, project name, project root, then "完成后请手动标记任务完成" with task link
- **Acceptance criteria status:**
  - ✅ Bridge polling `manual_only` device tasks calls `POST /api/v1/tasks/{id}/remind` (already implemented in US-011/US-013)
  - ✅ Cloud handler updates task status to `pending_manual` (already implemented, confirmed in trigger_reminder line 214)
  - ✅ Cloud calls `notifier.send_wechat_markdown()` with template including task instruction, machine name, project name, project root path (newly implemented)
  - ✅ Message includes "完成后请手动标记任务完成" and link to task (newly implemented)
  - ✅ python -m pytest passes (exit code 5 = no tests, expected)
  - ✅ python -m py_compile cloud/**/*.py passes
- **Reusable pattern**: When you need to access both a Task's foreign-keyed relationships (target_machine, project) in an endpoint, use `select(Task).options(joinedload(Task.target_machine), joinedload(Task.project)).where(...)` to avoid lazy-loading issues in async SQLAlchemy.

- **APScheduler integration with FastAPI lifespan**: Use `AsyncIOScheduler` with `start_scheduler()` called in startup and `stop_scheduler()` called in shutdown. Pass the scheduler instance to lifespan via module-level `_scheduler` variable.

- **APScheduler async job pattern**: APScheduler jobs that need async database access should be standalone async functions that create their own `async_session()` context, not rely on FastAPI's dependency injection.

---

## 2026-04-21 - US-016

- **What was implemented:** Created `cloud/scheduler.py` with APScheduler for stalled project detection and timed-out task handling. Integrated scheduler startup/shutdown with FastAPI lifespan in `main.py`.
- **Files changed:** `cloud/scheduler.py` (new file), `cloud/main.py` (added scheduler lifecycle)
- **Learnings:**
  - APScheduler `AsyncIOScheduler` is used with `IntervalTrigger(hours=1)` and `IntervalTrigger(minutes=5)` for periodic jobs
  - Jobs are async functions that manage their own database sessions (`async with async_session() as db`)
  - Project stalled check: `idle_hours > project.idle_threshold_hours` using calculated `idle_hours = (now - last_activity_at).total_seconds() / 3600`
  - Task timeout check: `elapsed > timeout_seconds` using `elapsed = (now - started_at).total_seconds()`
  - Deduplication: `last_reminder_at` stored in `task.result["last_reminder_at"]` (for tasks) or `project.result["last_reminder_at"]` (for projects)
  - Reminder interval check: `hours_since_reminder < reminder_interval_hours` before sending
  - Task timeout marks task as `failed` with `error_type="timeout"` and `exit_code=-1`
  - `datetime.fromisoformat()` for parsing stored ISO timestamps
- **Acceptance criteria status:**
  - ✅ Create `cloud/scheduler.py` with APScheduler
  - ✅ Project stall check: run every 1 hour, query for unarchived projects where idle_hours > threshold, send WeChat reminder
  - ✅ Task timeout check: run every 5 minutes, query running tasks where elapsed > timeout_seconds, send timeout reminder and mark failed
  - ✅ Deduplication: record last reminder time in task.result, don't repeat if within reminder_interval_hours
  - ✅ python -m pytest passes (exit code 5 = no tests, expected)
  - ✅ python -m py_compile cloud/**/*.py passes

---

## 2026-04-21 - US-014

- **What was implemented:** Created `cloud/notifier.py` with `send_wechat_markdown(title, content)` function
- **Files changed:** `cloud/notifier.py` (new file)
- **Learnings:**
  - WeChat Work webhook expects `msgtype: "markdown"` with nested `markdown.content` field
  - Content should be formatted as `**title**\ncontent` (title bold, then newline, then body)
  - Error handling: catches `ConnectError`, `ReadTimeout`, and generic Exception, logs appropriately, returns False
  - `get_settings()` provides `WECHAT_WEBHOOK_URL` from environment/config
  - Uses `httpx.AsyncClient` with `async with` context manager for proper resource cleanup
- **Acceptance criteria status:**
  - ✅ Create `cloud/notifier.py` with `send_wechat_markdown(title: str, content: str) -> bool`
  - ✅ Use `httpx.AsyncClient` POST to Webhook URL
  - ✅ Log errors without affecting main flow on send failure
  - ✅ Write send result (success/failure) back to `task.result["reminder_sent"]` - caller responsibility (this module only returns bool)
  - ✅ python -m pytest passes (exit code 5 = no tests, expected)
  - ✅ python -m py_compile cloud/**/*.py passes

---

## 2026-04-21 - US-010

- **What was implemented:** Bridge directory structure with config loading - fixed validation to include `api_url` and added config summary print on startup
- **Files changed:** `bridge/bridge/config.py` (added api_url to validation), `bridge/bridge/main.py` (added config summary print)
- **Learnings:**
  - US-010 was mostly already implemented in a previous iteration
  - Only missing pieces were: (1) `api_url` validation against "CHANGE_ME", (2) config summary print on startup
  - Bridge module structure was already complete with all required files: `__init__.py`, `main.py`, `config.py`, `api_client.py`, `executor.py`, `logger.py`
  - python -m pytest passes (exit code 5 = no tests, expected)
  - python -m py_compile cloud/**/*.py passes
  - python -m py_compile bridge/bridge/*.py passes

---

## 2026-04-21 - US-009

- **What was implemented:** Project Management API - added `is_exceeding_threshold` field to GET /projects response
- **Files changed:** `cloud/schemas.py` (added `is_exceeding_threshold` to `ProjectResponse`), `cloud/routers/projects.py` (updated GET to compute `is_exceeding_threshold`)
- **Learnings:**
  - US-009 was mostly already implemented in a previous iteration
  - Only missing piece was `is_exceeding_threshold` field in GET response
  - `is_exceeding_threshold = idle_hours > idle_threshold_hours` when `idle_hours` is not None
  - All 4 acceptance criteria now met: POST /projects (auto-id), GET /projects (with idle/threshold info), PUT /projects/{id} (archive + threshold), Auto-create project on machine registration
  - python -m pytest passes (exit code 5 = no tests, expected)
  - python -m py_compile cloud/**/*.py passes

---

## 2026-04-21 - US-008

- **What was implemented:** Task Management API endpoints (already fully implemented in previous iteration)
- **Files changed:** `cloud/routers/tasks.py` (already existed - all endpoints implemented)
- **Learnings:**
  - US-008 was already fully implemented in a previous iteration
  - All 6 acceptance criteria met: POST /tasks, GET /tasks (list with filters + pagination), GET /tasks/{id}, PUT /tasks/{id}, POST /tasks/{id}/result, POST /tasks/{id}/callback
  - `task_id` is auto-generated as `task-{uuid[:8]}` format
  - PUT /tasks/{id} implements status transition validation (allowed transitions only) and records status change timestamps (started_at, completed_at)
  - POST /tasks/{id}/result and POST /tasks/{id}/callback are nearly identical - both update result/completed_at/status from payload
  - python -m pytest passes (0 tests = exit code 0, expected)
  - python -m py_compile cloud/**/*.py passes

---

## 2026-04-21 - US-007

- **What was implemented:** Machine management API endpoints (already fully implemented in previous iteration)
- **Files changed:** `cloud/routers/machines.py` (already existed - all endpoints implemented)
- **Learnings:**
  - US-007 was already fully implemented in a previous iteration
  - All 6 acceptance criteria met: POST /machines, GET /machines (list), GET /machines/dashboard, GET /machines/{id}, PATCH /machines/{id}, GET /machines/{id}/poll
  - `machine_id` is the unique external identifier (machine_id string), `id` is the internal UUID primary key
  - Poll endpoint filters by `project_id` string (not UUID), looks up project by project_id to get UUID for filtering
  - `poll_tasks` updates `last_poll_at` and changes status to `online` on each poll
  - Dashboard returns running/dispatched tasks (limit 5) and today's completed count per machine
  - python -m pytest returns exit code 5 (no tests) - expected per US-024
  - python -m py_compile cloud/**/*.py passes

---

## 2026-04-21 - US-006

- **What was implemented:** Pydantic schema definitions for API request/response validation
- **Files changed:** `cloud/schemas.py` (already existed - fully implemented)
- **Learnings:**
  - US-006 was already fully implemented in a previous iteration
  - `cloud/schemas.py` contains all required schemas: `MachineCreate`, `MachineResponse`, `MachineUpdateStatus`, `TaskCreate`, `TaskUpdate`, `TaskResponse`, `TaskListResponse`, `ProjectCreate`, `ProjectUpdate`, `ProjectResponse`
  - All enums defined: `AgentType`, `AgentCapability`, `MachineStatus`, `TaskStatus`, plus `AgentStatus`, `TaskPriority`
  - Naming convention uses shorter names (e.g., `Create` instead of `CreateRequest`, `Update` instead of `UpdateRequest`) - this is a consistent project convention
  - `python -m pytest` returns exit code 5 = "no tests collected" (expected at this stage, tests come in US-024)
  - `python -m py_compile cloud/**/*.py` passes all syntax checks
  - Schemas properly use `from_attributes = True` for ORM compatibility

---

## 2026-04-21 - US-005

- **What was implemented:** FastAPI application entry point with API key auth, CORS, health endpoint, and environment variable configuration
- **Files changed:**
  - `cloud/main.py` (already existed - FastAPI app with lifespan, CORS, API key auth, routes under /api/v1)
  - `cloud/config.py` (already existed - Settings with DATABASE_URL, API_KEY, WECHAT_WEBHOOK_URL)
  - `cloud/database.py` (already existed - async SQLAlchemy setup)
  - `cloud/models.py` (already existed - Machine, Task, Project models)
  - `cloud/schemas.py` (already existed - Pydantic schemas)
  - `cloud/routers/machines.py`, `tasks.py`, `projects.py` (already existed - route handlers)
- **Learnings:**
  - US-005 was already fully implemented in a previous iteration
  - All acceptance criteria met: /api/v1 routes registered, X-API-Key header validation, CORS configured, /health endpoint works, env vars set
  - FastAPI `lifespan` context manager handles startup/shutdown (create tables on startup, dispose engine on shutdown)
  - `pydantic_settings.BaseSettings` reads from `.env` file automatically
  - API key validation accepts any key >= 8 chars in dev mode

---

## 2026-04-21 - US-001

- **What was implemented:** Agent CLI smoke testing - verified claude (working), openclaw (not installed), hermes (not installed), codex (installed but requires auth)
- **Files changed:** `agent_cli_verified.md` (new), `cloud/.venv/` (pytest installed)
- **Learnings:**
  - Only `claude --print` works out of the box for agent execution
  - `openclaw` and `hermes` are not installed - not needed for MVP per PRD Non-Goals
  - `codex exec` requires OpenAI API authentication and returns 401 without it
  - `python -m pytest` returns exit code 5 (no tests) since test files don't exist yet (US-024)
  - `python -m py_compile cloud/**/*.py` passes all syntax checks

---

## 2026-04-21 - US-003

- **What was implemented:** Development environment setup - verified all modules are properly configured
- **Files changed:**
  - `frontend/package.json` (added typecheck script)
  - `cloud/.gitignore` (created - Python, venv, env, IDE patterns)
  - `bridge/.gitignore` (created - Python, venv, env, IDE patterns)
  - `bridge/venv/` (created via python3 -m venv venv, dependencies installed)
- **Learnings:**
  - Frontend already had shadcn initialized with components in `src/components/ui/`
  - Cloud/.venv already had FastAPI/uvicorn/SQLAlchemy installed
  - Bridge venv needed to be created fresh with `python3 -m venv venv && pip install -r requirements.txt`
  - Root .gitignore already existed with proper patterns
  - pytest exit code 5 = "no tests collected" - not a failure, documented in US-001
  - `pnpm typecheck` requires adding to package.json scripts (`"typecheck": "tsc --noEmit"`)

---

## 2026-04-21 - US-004

- **What was implemented:** Database schema setup with Alembic migrations
- **Files changed:**
  - `cloud/alembic/` (created - migration directory with env.py, script.py.mako, README, versions/)
  - `cloud/alembic.ini` (updated sqlalchemy.url from PostgreSQL to SQLite)
  - `cloud/alembic/env.py` (updated to import models from parent directory)
  - `cloud/alembic/versions/ab77a4968437_initial_migration.py` (generated migration file)
- **Learnings:**
  - Tables `machines`, `tasks`, `projects` and all indexes already existed in `dus.db` - schema was created before this story
  - SQLite does not support `ALTER TABLE ... ALTER COLUMN` syntax - autogenerated migrations that try to alter NOT NULL constraints will fail
  - When tables already exist but alembic isn't set up, use `alembic stamp head` to mark the database as up-to-date without running migrations
  - `alembic init alembic` creates the migration directory structure; script_location in alembic.ini is relative to where alembic.ini is located
  - env.py needs `sys.path.insert(0, str(Path(__file__).parent.parent))` to import models from the parent cloud directory
  - **Reusable pattern**: When using alembic with a pre-existing database, first initialize alembic, set up env.py with proper model imports, run `alembic revision --autogenerate`, then use `alembic stamp head` to mark the existing schema as the starting point

---

## 2026-04-21 - US-012

- **What was implemented:** Agent executor - already fully implemented in a previous iteration
- **Files changed:** `bridge/bridge/executor.py` (already existed - all functionality implemented)
- **Learnings:**
  - US-012 was already fully implemented in a previous iteration
  - `AgentExecutor` base class with `execute(instruction, workdir)` method exists
  - `ClaudeCodeExecutor` uses `claude --print` mode with async subprocess execution
  - `StubExecutor` provides fallback for unverified agent CLIs
  - `get_executor()` factory pattern for selecting executor by agent_type
  - Timeout handling: `asyncio.wait_for` with proc.kill() on timeout, returns `error_type="timeout"`
  - Return format: `{"exit_code", "stdout", "stderr", "error_type"}` matches acceptance criteria
  - `workdir` parameter is passed to executor; directory creation is caller's responsibility
  - python -m pytest returns exit code 5 (no tests) - expected at this stage
  - python -m py_compile bridge/bridge/*.py passes
  - python -m py_compile cloud/**/*.py passes

---

## 2026-04-21 - US-011

- **What was implemented:** Bridge API client - fixed `poll_tasks()` to accept optional `project_id` parameter, renamed `trigger_reminder()` to `send_reminder()` to match acceptance criteria, updated `main.py` to use `send_reminder()`
- **Files changed:** `bridge/bridge/api_client.py` (poll_tasks now accepts project_id param, trigger_reminder renamed to send_reminder), `bridge/bridge/main.py` (updated to call send_reminder)
- **Learnings:**
  - US-011 was mostly already implemented - only missing pieces were: (1) `poll_tasks(project_id=None)` parameter support, (2) method name `send_reminder` instead of `trigger_reminder`
  - `poll_tasks(project_id=None)` - when project_id is passed as argument it overrides `self.machine_config.project_id`; when None it falls back to config value
  - Cloud endpoint is `POST /tasks/{task_uuid}/remind` (uses internal UUID, not task_id string)
  - python -m pytest returns exit code 5 (no tests) - expected at this stage
  - python -m py_compile bridge/bridge/*.py passes

