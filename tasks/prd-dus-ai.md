# PRD: DUS 分布式AI终端统一调度系统 - 完整开发

## Overview

DUS（Distributed AI Terminal Unified Scheduling System）是一个用于统一管理和调度多台终端设备上 AI Agent 执行任务的管理平台。本 PRD 涵盖从 M0 预研到 M7 生产部署的完整开发计划，目标是在第一阶段 MVP 中实现：云端 FastAPI 单应用提供任务/设备/项目管理 API、设备端 Python Bridge 实现 60 秒轮询 + Agent 执行、支持 remote_execution 类 Agent 自动执行和 manual_only 类 Agent 企业微信提醒、基础 Web Dashboard、以及项目停滞提醒 + 任务超时提醒。

## Goals

- 完成 M0-M7 所有里程碑的开发
- 云端 FastAPI 提供完整的设备/任务/项目管理 API
- Bridge 部署在设备上实现自动轮询和 Claude Code 执行
- 企业微信 Webhook 集成实现 manual_only 任务提醒
- APScheduler 定时任务实现停滞项目 + 超时任务提醒
- Next.js Web Dashboard 四个页面完整可用
- 端到端测试验证完整链路
- 部署到 Railway + 前端可公网访问

## Quality Gates

These commands must pass for every user story:

**后端（Cloud）:**
- `python -m pytest` - 单元测试
- `python -m py_compile cloud/**/*.py` - 语法检查

**前端（Frontend）:**
- `pnpm typecheck` - TypeScript 类型检查
- `pnpm lint` - ESLint 检查

**UI 故事额外验证:**
- 使用 dev-browser skill 进行浏览器视觉验证

## User Stories

### US-001: 技术预研 - Agent CLI 冒烟测试
**Description:** As a developer, I want to verify all Agent CLI interfaces work correctly so that I can confirm the exact command formats before implementation.

**Acceptance Criteria:**
- [ ] Run `claude --print` smoke test and record output format
- [ ] Run `openclaw --task` smoke test and record output format
- [ ] Run `hermes chat --task` smoke test and record output format
- [ ] Run `codex --task` smoke test and record output format
- [ ] Document each Agent's actual command format, return structure, and exit codes in `agent_cli_verified.md`

### US-002: 技术预研 - 企业微信 Webhook 联调
**Description:** As a developer, I want to verify WeChat Work Webhook works correctly so that reminder messages can be sent.

**Acceptance Criteria:**
- [ ] Create WeChat Work group bot and obtain Webhook URL
- [ ] Manually curl POST test message to verify markdown rendering
- [ ] Document Webhook URL in `.env` (not committed to git)
- [ ] Record Webhook URL format and rate limits

### US-003: 技术预研 - 开发环境准备
**Description:** As a developer, I want the development environment properly set up so that all modules can be developed independently.

**Acceptance Criteria:**
- [ ] Git repository created with `cloud/`, `bridge/`, `frontend/` subdirectories
- [ ] `.gitignore` configured (`.env`, `*.pyc`, `node_modules` etc.)
- [ ] Cloud venv created with FastAPI/uvicorn/sqlalchemy dependencies installed
- [ ] Bridge dependencies installed (httpx/loguru/pyyaml)
- [ ] Frontend initialized with `npx shadcn@latest init --yes --template next --base-color neutral`

### US-004: M1 云端骨架 - 数据库建表
**Description:** As a developer, I want the database tables created so that the API can persist data.

**Acceptance Criteria:**
- [ ] Create `cloud/alembic/` migration directory
- [ ] Define SQLAlchemy models for `machines`, `tasks`, `projects` tables
- [ ] Generate migration file with `alembic revision --autogenerate`
- [ ] Execute `alembic upgrade head` to create tables
- [ ] Verify all indexes created: `idx_tasks_status`, `idx_tasks_target`, `idx_tasks_project`, `idx_machines_status`, `idx_machines_agent_type`

### US-005: M1 云端骨架 - FastAPI 应用入口
**Description:** As a developer, I want the FastAPI application entry point created so that the API can start and accept requests.

**Acceptance Criteria:**
- [ ] Create `cloud/main.py` with all routes registered under `/api/v1/`
- [ ] Implement API Key authentication middleware (`X-API-Key` header validation)
- [ ] Configure CORS to allow frontend cross-origin access
- [ ] Implement `/health` endpoint returning `{"status": "ok"}`
- [ ] Configure environment variables: `DATABASE_URL`, `API_KEY`, `WECHAT_WEBHOOK_URL`

### US-006: M1 云端骨架 - Pydantic Schema 定义
**Description:** As a developer, I want Pydantic schemas defined so that API requests and responses are validated.

**Acceptance Criteria:**
- [ ] Define `Machine` schemas: `CreateRequest`, `UpdateRequest`, `Response`
- [ ] Define `Task` schemas: `CreateRequest`, `UpdateRequest`, `Response`
- [ ] Define `Project` schemas: `CreateRequest`, `UpdateRequest`, `Response`
- [ ] Define enums: `AgentType`, `AgentCapability`, `MachineStatus`, `TaskStatus`

### US-007: M2 核心 API - 设备管理 API
**Description:** As a user, I want to manage machines through the API so that devices can register and be controlled.

**Acceptance Criteria:**
- [ ] `POST /api/v1/machines` - Register/update machine with unique `machine_id` validation
- [ ] `GET /api/v1/machines` - List machines with `status` / `agent_type` filtering
- [ ] `GET /api/v1/machines/dashboard` - Get dashboard data with all machines, running tasks, today's completion count
- [ ] `GET /api/v1/machines/{id}` - Get machine details with unfinished task count
- [ ] `PATCH /api/v1/machines/{id}` - Update `is_enabled` and `status`
- [ ] `GET /api/v1/machines/{id}/poll` - Poll tasks, update `last_poll_at`, support `?project_id=` filtering, return `pending` tasks and batch update to `dispatched`

### US-008: M2 核心 API - 任务管理 API
**Description:** As a user, I want to manage tasks through the API so that work can be dispatched and tracked.

**Acceptance Criteria:**
- [ ] `POST /api/v1/tasks` - Create task with auto-generated `task_id` (`task-{uuid[:8]}`), validate `target_machine_id` exists
- [ ] `GET /api/v1/tasks` - List tasks with `status` / `project_id` / `target_machine_id` filtering and pagination (`limit` + `offset`)
- [ ] `GET /api/v1/tasks/{id}` - Get task details including `result` JSONB
- [ ] `PUT /api/v1/tasks/{id}` - Update task `status` only, record status change timestamp
- [ ] `POST /api/v1/tasks/{id}/result` - Bridge submits execution result, update `result` / `completed_at` / `status`
- [ ] `POST /api/v1/tasks/{id}/callback` - Device callback to report results via Hook script

### US-009: M2 核心 API - 项目管理 API
**Description:** As a user, I want to manage projects through the API so that tasks can be organized by project.

**Acceptance Criteria:**
- [ ] `POST /api/v1/projects` - Create project with auto-generated `project_id`
- [ ] `GET /api/v1/projects` - List projects with `last_activity_at`, idle hours, and whether exceeding `idle_threshold_hours`
- [ ] `PUT /api/v1/projects/{id}` - Update project (archive with `is_archived = true`, modify threshold)
- [ ] Auto-create project when Bridge registers with `project_id` that doesn't exist

### US-010: M3 设备 Bridge - 目录结构和配置加载
**Description:** As a developer, I want the Bridge directory structure created and config loading implemented so that Bridge can run.

**Acceptance Criteria:**
- [ ] Create `bridge/bridge/` package structure with `__init__.py`, `main.py`, `config.py`, `api_client.py`, `executor.py`, `logger.py`
- [ ] `config.py` reads `config.yaml` with environment variable override support
- [ ] Validate required fields (`machine_id`, `api_key`, `api_url` cannot be `CHANGE_ME`)
- [ ] Print config summary on startup

### US-011: M3 设备 Bridge - API 客户端实现
**Description:** As a Bridge developer, I want the API client implemented so that Bridge can communicate with the cloud.

**Acceptance Criteria:**
- [ ] Implement `register_machine()` - Register this machine on startup
- [ ] Implement `poll_tasks(project_id=None)` - Pull pending tasks, support project filtering
- [ ] Implement `update_task_status(task_id, status)` - Update task status
- [ ] Implement `submit_result(task_id, result)` - Submit execution result
- [ ] Implement `send_reminder(task_id)` - Trigger WeChat reminder
- [ ] All requests include `X-API-Key` header
- [ ] Network timeout: connect=5s, read=30s
- [ ] Retry strategy: max 3 retries on network error, 2s interval

### US-012: M3 设备 Bridge - Agent 执行器实现
**Description:** As a Bridge developer, I want the Agent executor implemented so that tasks can be executed on the device.

**Acceptance Criteria:**
- [ ] Create base `AgentExecutor` class with `execute(instruction: str, workdir: str) -> dict`
- [ ] Return format: `{"exit_code": int, "stdout": str, "stderr": str, "error_type": str | None}`
- [ ] Implement `ClaudeCodeExecutor` with command: `claude --print "{instruction}"`
- [ ] Create working directory: `/tmp/dus_task_{task_id}/` before execution
- [ ] Read timeout from `task.timeout_seconds` (default 3600s)
- [ ] Kill subprocess on timeout, return `error_type = "timeout"`

### US-013: M3 设备 Bridge - 主轮询循环
**Description:** As a Bridge developer, I want the main polling loop implemented so that Bridge continuously fetches and executes tasks.

**Acceptance Criteria:**
- [ ] `main()` async function calls `register_machine()` on startup
- [ ] Main loop polls tasks every `config.poll_interval` (default 60s)
- [ ] `handle_task()` creates asyncio task for each pending task
- [ ] `remote_execution` tasks call `execute_remote()`
- [ ] `manual_only` tasks call `send_manual_reminder()`
- [ ] Concurrent execution limit: `asyncio.Semaphore(3)`
- [ ] Graceful `Ctrl+C` shutdown waiting for running tasks

### US-014: M4 提醒系统 - 企业微信 Webhook 发送模块
**Description:** As a developer, I want the WeChat Webhook module implemented so that reminder messages can be sent.

**Acceptance Criteria:**
- [ ] Create `cloud/notifier.py` with `send_wechat_markdown(title: str, content: str) -> bool`
- [ ] Use `httpx.AsyncClient` POST to Webhook URL
- [ ] Log errors without affecting main flow on send failure
- [ ] Write send result (success/failure) back to `task.result["reminder_sent"]`

### US-015: M4 提醒系统 - Windsurf 任务提醒
**Description:** As a user, I want Windsurf tasks to trigger WeChat reminders so that I know to manually execute them.

**Acceptance Criteria:**
- [ ] Bridge polling `manual_only` device tasks calls `POST /api/v1/tasks/{id}/remind`
- [ ] Cloud handler updates task status to `pending_manual`
- [ ] Cloud calls `notifier.send_wechat_markdown()` with template including task instruction, machine name, project name, project root path
- [ ] Message includes "完成后请手动标记任务完成" and link to task

### US-016: M4 提醒系统 - APScheduler 定时提醒
**Description:** As a user, I want automatic reminders for stalled projects and timed-out tasks so that I can take action.

**Acceptance Criteria:**
- [ ] Create `cloud/scheduler.py` with APScheduler
- [ ] Project stall check: run every 1 hour, query `last_activity_at < NOW() - idle_threshold_hours`, send WeChat reminder for unarchived projects
- [ ] Task timeout check: run every 5 minutes, query `status = 'running' AND started_at + timeout_seconds < NOW()`, send timeout reminder and mark `failed`
- [ ] Deduplication: record last reminder time in `task.result`, don't repeat if within `reminder_interval_hours`

### US-017: M5 Web Dashboard - 项目初始化与基础配置
**Description:** As a developer, I want the frontend project initialized and configured so that UI development can begin.

**Acceptance Criteria:**
- [ ] Initialize with `npx shadcn@latest init --yes --template next --base-color neutral`
- [ ] Install dependencies: `pnpm add @tanstack/react-query zustand zod react-hook-form clsx`
- [ ] Configure `next.config.js` with API proxy rewrite `/api/* → http://localhost:8000/api/*`
- [ ] Create `app/lib/api.ts`封装 fetch, inject API Key header, integrate TanStack Query
- [ ] Initialize shadcn components: `npx shadcn add button card badge dialog form input select textarea`

### US-018: M5 Web Dashboard - App Router 路由结构
**Description:** As a developer, I want the App Router structure created so that pages can be implemented.

**Acceptance Criteria:**
- [ ] `app/page.tsx` redirects to `/tasks`
- [ ] `app/layout.tsx` root layout with global Provider injection
- [ ] Create `app/lib/` with `api.ts`, `utils.ts`, `store.ts`
- [ ] Create `app/components/ui/` with shadcn components
- [ ] Create `app/components/device-card.tsx`, `task-card.tsx`, `status-badge.tsx`, `task-create-modal.tsx`
- [ ] Create route pages: `/devices/page.tsx`, `/tasks/page.tsx`, `/tasks/[id]/page.tsx`, `/projects/page.tsx`

### US-019: M5 Web Dashboard - 设备列表页 `/devices`
**Description:** As a user, I want to view and manage all devices from a dashboard so that I can monitor device status and dispatch tasks.

**Acceptance Criteria:**
- [ ] Device card dashboard layout replacing original stats cards + recent tasks
- [ ] Each device card shows: name, online status, availability (enabled/disabled), busy status, running tasks, today's completion count, last heartbeat
- [ ] Click device card to quickly dispatch task (Dialog popup)
- [ ] Click "Enable/Disable" button to manage device availability
- [ ] Polling interval: 10 seconds (`refetchInterval: 10000`)

### US-020: M5 Web Dashboard - 任务列表页 `/tasks`
**Description:** As a user, I want to view and create tasks so that I can manage all task operations.

**Acceptance Criteria:**
- [ ] Top status filter tabs: All / Pending / Running / Success / Failed
- [ ] Top-right "+ New Task" floating action button
- [ ] Each row shows: task ID, title, target device, status badge, created time, action buttons (view/cancel)
- [ ] Windsurf task special display: "Reminder sent, please login manually to execute"
- [ ] Polling interval: 5 seconds
- [ ] New task dialog (shadcn Dialog + react-hook-form + zod validation)

### US-021: M5 Web Dashboard - 任务详情页 `/tasks/:id`
**Description:** As a user, I want to view task details so that I can track execution progress and results.

**Acceptance Criteria:**
- [ ] Task basic info card (title, status, target device, project)
- [ ] Execution progress display (dynamic animation for `running` status)
- [ ] Windsurf reminder info display (shown for `pending_manual` status)
- [ ] Execution result display (`result.stdout` / `result.stderr` in code block format)
- [ ] Error message display (`error_message` in red highlight when non-empty)
- [ ] "Mark Complete" button (available for `pending_manual` status)
- [ ] "Cancel Task" button (available for `pending` / `dispatched` / `running` status)
- [ ] Polling interval: 3 seconds (dynamic adjustment when task is running)

### US-022: M5 Web Dashboard - 项目状态页 `/projects`
**Description:** As a user, I want to view project status so that I can identify stalled projects.

**Acceptance Criteria:**
- [ ] Display all project cards
- [ ] Each card shows: project name, project path, last activity time, idle duration, idle status (normal/warning/overdue)
- [ ] Idle status color rules: under threshold = green, within 2x threshold = yellow warning, over 2x = red overdue
- [ ] Polling interval: 30 seconds

### US-023: M5 Web Dashboard - 状态徽章组件 StatusBadge
**Description:** As a developer, I want the StatusBadge component created so that consistent status display is used across all pages.

**Acceptance Criteria:**
- [ ] Create `components/status-badge.tsx` with shadcn Badge
- [ ] Define variants for: pending, dispatched, running, completed, failed, cancelled, pending_manual, online, offline
- [ ] Each variant has correct color scheme and Chinese label
- [ ] Component is reusable across all pages

### US-024: M6 端到端测试 - 单元测试
**Description:** As a developer, I want unit tests written so that API correctness can be verified.

**Acceptance Criteria:**
- [ ] `cloud/tests/test_api.py` uses `httpx.AsyncClient` + `pytest-asyncio` to test all API endpoints
- [ ] `bridge/tests/test_executor.py` mocks subprocess, tests ClaudeCodeExecutor return structure
- [ ] `bridge/tests/test_api_client.py` mocks HTTP responses, tests retry logic

### US-025: M6 端到端测试 - 集成测试链路
**Description:** As a developer, I want integration tests run so that the complete system works end-to-end.

**Acceptance Criteria:**
- [ ] Chain A (Remote Execution): Start cloud → Start Bridge → Create task → Observe pending → dispatched → running → completed
- [ ] Chain B (Windsurf Reminder): Create manual_only device → Create task → Start Bridge → Observe pending_manual status + WeChat message received
- [ ] Chain C (Timeout Handling): Create task with timeout_seconds=10 → Execute sleep 30 → Observe timeout error_type returned → Task marked failed
- [ ] Chain D (Web Dashboard): Test /devices page with 10s auto-refresh → Test /tasks page with new task dialog → Create task and observe 5s auto-refresh → Click task for detail page → Verify result display

### US-026: M7 生产部署 - 云端部署到 Railway
**Description:** As a developer, I want the cloud deployed to Railway so that it can be accessed publicly.

**Acceptance Criteria:**
- [ ] Create Railway project with PostgreSQL plugin
- [ ] Add Web Service connected to GitHub `cloud/` directory
- [ ] Configure environment variables: `DATABASE_URL`, `API_KEY`, `WECHAT_WEBHOOK_URL`
- [ ] Trigger first deployment, verify `/health` returns 200
- [ ] Run `alembic upgrade head` via Railway Console
- [ ] Verify `/docs` Swagger UI accessible

### US-027: M7 生产部署 - 前端部署
**Description:** As a developer, I want the frontend deployed so that the dashboard can be accessed publicly.

**Acceptance Criteria:**
- [ ] Build with `pnpm build` (outputs `.next/` directory)
- [ ] Deploy to hosting platform (ECS+PM2 recommended for China, or Vercel for overseas)
- [ ] Configure `NEXT_PUBLIC_API_BASE_URL` and `API_KEY` environment variables
- [ ] Verify dashboard accessible at public URL
- [ ] Verify API calls work correctly to cloud endpoint

### US-028: M7 生产部署 - Bridge 上线
**Description:** As an operator, I want Bridge deployed on target devices so that tasks can be executed.

**Acceptance Criteria:**
- [ ] Document git clone and install instructions
- [ ] Provide `launchd` plist example for macOS auto-start
- [ ] Provide `systemd` unit example for Linux auto-start
- [ ] Verify Bridge runs continuously for at least 1 hour without crash

## Functional Requirements

- FR-1: All API endpoints must use `X-API-Key` header authentication
- FR-2: All API responses must follow unified format: `{"success": true, "data": {...}, "message": "ok"}`
- FR-3: Task status transitions must follow: pending → dispatched → running → completed/failed
- FR-4: Machine status (online/offline) must be maintained by heartbeat (last_poll_at)
- FR-5: APScheduler must mark machines offline if `last_poll_at` exceeds 120 seconds
- FR-6: Bridge must handle network errors gracefully without interrupting polling loop
- FR-7: All timestamps must use UTC
- FR-8: Database must use PostgreSQL in production, SQLite in development
- FR-9: Frontend must use TanStack Query for all API data fetching
- FR-10: Frontend must implement optimistic updates where appropriate

## Non-Goals

The following are explicitly out of scope for this MVP:
- Device autonomous task claiming / load balancing
- WebSocket real-time push
- Redis queue
- File activity monitoring (watchdog)
- Multi-user permission system
- Email / Slack reminder channels
- openclaw / hermes_agent / codex executors (only claude_code is required)
- Dark mode support

## Technical Considerations

- Agent CLI command formats must be verified during M0 pre-research before M3 implementation
- WeChat Work Webhook has rate limits (20 messages/minute per group)
- Railway PostgreSQL connection string format: `postgresql+asyncpg://`
- Next.js rewrites must correctly proxy API requests to cloud backend
- Bridge must work behind NAT; cloud does not need to reach Bridge directly
- Claude Code must be in PATH or `agent.path` config must be specified

## Success Metrics

- All API endpoints return 200/201 with correct response format
- Bridge successfully polls and executes tasks within 60 seconds
- WeChat reminder messages received within 1 minute of trigger
- Web Dashboard all four pages load and display data correctly
- TanStack Query auto-refresh works without page reload
- End-to-end test chains A/B/C/D all pass
- System runs stably on Railway for at least 1 hour

## Open Questions

- Should `claude --print` require PTY mode for certain instructions?
- Does Claude Code version need to be >= 1.0.4 for `--print` flag?
- Should we implement automatic retry with exponential backoff for WeChat Webhook failures?
- Should project `last_activity_at` be automatically updated when Bridge registers or polls?
- Should task results be retained indefinitely or archived after a certain period?