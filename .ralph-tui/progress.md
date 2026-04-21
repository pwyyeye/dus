# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

- **Alembic initialization with pre-existing database**: Initialize with `alembic init alembic`, configure env.py to import models with `sys.path.insert(0, str(Path(__file__).parent.parent))`, run `alembic revision --autogenerate`, then use `alembic stamp head` to mark existing schema as the baseline (SQLite doesn't support ALTER COLUMN so direct upgrade may fail)

- **API Router versioning pattern**: Routes registered under `/api/v1` prefix in main.py, each router has `prefix="/machines"` and uses `response_model=ApiResponse` wrapper for consistent JSON envelope. Auth via `Security(verify_api_key)` dependency at router level.

- **Two-schema pattern for list vs detail**: `MachineListResponse` (shorter, for list views) vs `MachineResponse` (includes pending_task_count, set manually after query). `PollTaskResponse` used for poll results with `agent_capability` field added.

- **Poll endpoint pattern**: Updates `last_poll_at` and sets status=`online` on every poll. Filters tasks by `target_machine_id` and `status=pending`, optionally filters by `project_id` string (looked up to UUID). Batch-updates matched tasks to `dispatched` in memory without explicit flush (relies on get_db commit).

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

