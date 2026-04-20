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
| GET | `/machines/{uuid}/poll` | 机器轮询任务（支持 `?project_id=` 过滤） |

### 任务管理 `/api/v1/tasks`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建任务 |
| GET | `/tasks` | 任务列表（支持 status、project_id、target_machine_id 过滤） |
| GET | `/tasks/{uuid}` | 任务详情 |
| PUT | `/tasks/{uuid}` | 更新任务状态 |
| POST | `/tasks/{uuid}/callback` | 设备回调上报结果（Hook） |
| POST | `/tasks/{uuid}/result` | 提交任务执行结果（Bridge 调用） |
| POST | `/tasks/{uuid}/remind` | 触发手动任务提醒 |

### 项目管理 `/api/v1/projects`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/projects` | 创建项目 |
| GET | `/projects` | 项目列表（含空闲时长） |
| PUT | `/projects/{uuid}` | 更新项目设置 |

## 数据模型

### Machine（机器）

| 字段 | 类型 | 说明 |
|------|------|------|
| `machine_id` | string | 机器唯一标识（如 `macbook-pro-office`） |
| `machine_name` | string | 展示名称 |
| `agent_type` | enum | 代理类型：claude_code / openclaw / hermes_agent / codex / windsurf |
| `agent_capability` | enum | 能力：remote_execution（远程执行）/ manual_only（仅提醒） |
| `status` | enum | online / offline |
| `is_enabled` | bool | 是否启用（禁用后不接收新任务） |
| `agent_status` | enum | idle / busy / offline（Claude Code 执行状态） |

### Task（任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| `instruction` | string | 执行指令（核心字段） |
| `project_id` | uuid | 关联的项目 |
| `target_machine_id` | uuid | 指定的执行设备 |
| `status` | enum | pending / dispatched / running / completed / failed / cancelled |
| `result` | json | 执行结果：{exit_code, stdout, stderr, error_type} |
| `error_message` | string | 错误信息 |

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
