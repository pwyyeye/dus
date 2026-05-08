# DUS Cloud API

分布式AI终端统一调度系统 - 云端调度中心

## 技术栈

- **FastAPI** - Web 框架
- **SQLAlchemy 2.0** (asyncio) - ORM
- **PostgreSQL** / **SQLite** - 数据库
- **Alembic** - 数据库迁移

## 项目结构

```
cloud/
├── main.py              # FastAPI 应用入口
├── config.py            # 配置管理 (pydantic-settings)
├── database.py          # 数据库连接
├── models.py            # SQLAlchemy 模型
├── schemas.py           # Pydantic 请求/响应模型
├── routers/
│   ├── machines.py      # 机器管理 API
│   ├── tasks.py         # 任务管理 API
│   ├── issues.py        # Issue 管理 API
│   └── projects.py      # 项目管理 API
├── alembic.ini          # Alembic 配置
└── .env                 # 环境变量
```

## 快速开始

### 1. 安装依赖

```bash
cd cloud
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入数据库连接和 API Key
```

关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接 | `sqlite+aiosqlite:///./dus.db` |
| `API_KEY` | API 认证密钥 | `change-me` |
| `WECHAT_WEBHOOK_URL` | 企业微信 Webhook | 空 |
| `FRONTEND_URL` | 前端地址（用于 CORS） | `http://localhost:3000` |

### 3. 启动服务

```bash
# 开发模式（热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. 数据库迁移（生产环境使用 PostgreSQL 时）

```bash
alembic upgrade head
```

## API 文档

启动服务后访问：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 认证

所有 API（除 `/health` 外）需要通过 `X-API-Key` Header 认证：

```
X-API-Key: your-api-key
```

## 端点概览

### 健康检查

- `GET /health` - 服务健康状态

### 机器管理 `/api/v1/machines`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/machines` | 注册/更新机器（支持自动创建项目） |
| GET | `/machines` | 机器列表（支持 status、agent_type 过滤） |
| GET | `/machines/dashboard` | 仪表盘数据（含运行中任务、今日完成数） |
| GET | `/machines/{uuid}` | 机器详情（含待执行任务数） |
| PATCH | `/machines/{uuid}` | 更新机器状态（启用/禁用、agent状态） |
| GET | `/machines/{uuid}/poll` | 机器轮询任务（含 Issue 上下文和 session 恢复信息） |

### 任务管理 `/api/v1/tasks`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建任务（支持关联 Issue） |
| GET | `/tasks` | 任务列表（支持 status、project_id、target_machine_id 过滤） |
| GET | `/tasks/{uuid}` | 任务详情 |
| PUT | `/tasks/{uuid}` | 更新任务状态 |
| POST | `/tasks/{uuid}/callback` | 设备回调上报结果（Hook） |
| POST | `/tasks/{uuid}/result` | 提交任务执行结果（含 session_id/work_dir） |
| PUT | `/tasks/{uuid}/pin` | 运行时固定 session_id 和 work_dir（用于崩溃恢复） |
| POST | `/tasks/{uuid}/remind` | 触发手动任务提醒 |

### Issue 管理 `/api/v1/issues`

Issue 是工作单元，Task 是执行单元。一个 Issue 可包含多个 Task（执行历史）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/issues` | 创建 Issue（分配机器时自动派发 Task） |
| GET | `/issues` | Issue 列表（支持 status、project_id、assignee_id 过滤） |
| GET | `/issues/{uuid}` | Issue 详情（含执行历史 tasks） |
| PUT | `/issues/{uuid}` | 更新 Issue（改分配时自动取消旧 Task、创建新 Task） |
| DELETE | `/issues/{uuid}` | 删除 Issue（级联取消活跃 Task） |
| GET | `/issues/{uuid}/tasks` | 获取 Issue 的执行历史 |

### 项目管理 `/api/v1/projects`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/projects` | 创建项目 |
| GET | `/projects` | 项目列表（含空闲时长） |
| PUT | `/projects/{uuid}` | 更新项目设置 |

## 核心概念

### Issue-Task 分层模型

- **Issue** = 工作单元（如 "修复登录 bug"），包含标题、描述、状态、优先级、负责人
- **Task** = 执行单元（一次具体的远程执行），包含指令、执行结果、session 信息
- 一个 Issue 可产生多个 Task（改分配时取消旧 Task、创建新 Task；同一 Issue 多次执行）

### Session Resumption（会话恢复）

借鉴 Multica 的 session pinning 机制：

1. Bridge 执行任务时，Claude Code 可通过 `--resume <session_id>` 恢复之前的对话上下文
2. 任务完成后，Bridge 将 `session_id` 和 `work_dir` 随结果提交回 Cloud
3. 下次该 Issue 产生新 Task 时，Cloud 在 poll 响应中返回 `prior_session_id` 和 `prior_work_dir`
4. Bridge 使用这些信息恢复 Claude Code 会话，保持工作连续性

API 支持：
- `POST /tasks/{uuid}/result` / `callback` — 接受 `session_id` 和 `work_dir`
- `PUT /tasks/{uuid}/pin` — 运行中固定 session（崩溃恢复）
- `GET /machines/{uuid}/poll` — 返回 `prior_session_id` / `prior_work_dir`

## 数据模型

### Machine（机器）

| 字段 | 类型 | 说明 |
|------|------|------|
| `machine_id` | string | 机器唯一标识（如 `macbook-pro-office`） |
| `machine_name` | string | 展示名称 |
| `agent_type` | enum | 代理类型：claude_code / openclaw / hermes_agent / codex |
| `agent_capability` | enum | 能力：remote_execution（远程执行）/ manual_only（仅提醒） |
| `status` | enum | online / offline |
| `is_enabled` | bool | 是否启用（禁用后不接收新任务） |
| `agent_status` | enum | idle / busy / offline（Claude Code 执行状态） |
| `project_id` | uuid | 归属项目（自动领取/claim 时只允许该项目任务） |

### Task（任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| `instruction` | string | 执行指令（核心字段） |
| `project_id` | uuid | 关联的项目 |
| `target_machine_id` | uuid | 指定的执行设备 |
| `issue_id` | uuid | 关联的 Issue |
| `status` | enum | pending / dispatched / running / completed / failed / cancelled / pending_manual |
| `result` | json | 执行结果：{exit_code, stdout, stderr, error_type} |
| `error_message` | string | 错误信息 |
| `session_id` | string | Claude Code 会话 ID（用于恢复） |
| `work_dir` | string | 工作目录（用于恢复） |

### Issue（工作项）

| 字段 | 类型 | 说明 |
|------|------|------|
| `issue_id` | string | 可读唯一标识（如 `issue-a1b2c3d4`） |
| `title` | string | 标题 |
| `description` | string | 描述 |
| `status` | enum | todo / in_progress / done / cancelled |
| `priority` | enum | low / medium / high / urgent |
| `assignee_type` | string | 负责人类型（如 `machine`） |
| `assignee_id` | uuid | 负责人 ID |
| `project_id` | uuid | 关联项目 |

### Project（项目）

| 字段 | 类型 | 说明 |
|------|------|------|
| `project_name` | string | 项目名称 |
| `root_path` | string | 根目录路径 |
| `idle_threshold_hours` | int | 空闲阈值（小时），超时发送提醒 |
| `reminder_interval_hours` | int | 提醒间隔 |

## 任务状态流转

```
pending → dispatched → running → completed
                  ↘ failed ↗
         ↗ cancelled
pending_manual → completed / cancelled
```

## 环境变量参考

```bash
# 数据库（开发用 SQLite，生产用 PostgreSQL）
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/dus

# API 认证
API_KEY=change-me-to-a-strong-random-string

# 企业微信 webhook（可选，用于发送提醒）
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY

# 前端地址（CORS 配置）
FRONTEND_URL=http://localhost:3000
```

## License

Internal use only.
