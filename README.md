# DUS - 分布式AI终端统一调度系统

> **Distributed AI Terminal Unified Scheduling System**

一个用于统一管理和调度多台终端设备上 AI Agent（如 Claude Code）执行任务的管理平台。

---

## 核心功能

### 设备管理
- **设备注册与状态监控**：终端设备（Bridge）启动时自动注册，心跳维持在线状态
- **设备可用性控制**：支持启用/禁用设备，被禁用的设备不会收到新任务
- **多窗口支持**：同一设备可运行多个 Claude Code 窗口，每个窗口通过 `project_id` 拉取属于自己的任务

### Issue-Task 分层调度
- **Issue 工作单元**：以 Issue 为单位管理工作项（如 "修复登录 bug"），支持优先级、状态、负责人
- **Task 执行单元**：一个 Issue 可产生多个 Task，形成执行历史；改分配时自动取消旧 Task、创建新 Task
- **会话恢复（Session Resumption）**：借鉴 Multica 设计，任务完成后保存 `session_id` 和 `work_dir`，下次执行同一 Issue 时自动恢复 Claude Code 对话上下文，保持工作连续性

### 任务调度
- **指令下发**：向指定设备下发执行指令（Instruction）
- **项目绑定**：任务与项目（Project）绑定，不同项目可分配给不同设备
- **状态跟踪**：完整任务状态流转（pending → dispatched → running → completed/failed）
- **结果回调**：设备执行完成后通过 Hook 脚本回调上报结果（exit_code, stdout, stderr, session_id, work_dir）

### 前端管理
- **首页设备仪表盘**：卡片式展示所有设备状态、运行中任务，一键下发任务
- **设备管理**：查看设备列表、在线状态、Agent 类型
- **任务管理**：查看/创建任务，追踪执行状态
- **Issue 管理**：查看/创建 Issue，追踪执行历史和会话恢复状态
- **项目管理**：查看/创建项目，关联任务

---

### 日志监控子 Agent

一个后台日志监控系统，自动检测后端错误日志，并在 Agent 空闲时通知 Claude Code 处理。

**设计思路**：开发过程中后端可能产生错误日志，但 Agent 正忙于编码时不应被打断。本系统通过空闲检测机制，只在 Agent 空闲时才推送错误通知，避免干扰正在进行的工作。

#### 架构

```
log_monitor.py ──扫描──> 日志文件 (bridge-stdout.log, uvicorn.log 等)
     │
     ├─ 检测 Agent 空闲？──否──> 抑制通知（Agent 正在编码）
     │
     └─ 是 ──写入──> .dus/log_errors.json
                          │
                          └─ Claude Code 定时任务每 2 分钟读取 ──> 处理错误
```

#### 启动监控

```bash
D:/ProgramData/miniconda3/python.exe -u scripts/log_monitor.py
```

可选指定配置文件路径：

```bash
python -u scripts/log_monitor.py --config .dus/log_monitor.json
```

#### 配置说明

配置文件：`.dus/log_monitor.json`

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `log_files` | string[] | `[".dus/bridge-stdout.log", "cloud/uvicorn.log"]` | 要监控的日志文件列表 |
| `project_dir` | string | `"."` | 项目根目录 |
| `idle_threshold_seconds` | int | `30` | Agent 空闲判定阈值（秒），超过此时间无文件修改视为空闲 |
| `scan_interval_seconds` | int | `10` | 扫描间隔（秒） |
| `error_output` | string | `".dus/log_errors.json"` | 错误通知输出文件 |
| `error_patterns` | string[] | `ERROR, CRITICAL, Traceback, Exception:, 500 error, Internal Server Error` | 错误匹配正则表达式 |
| `ignore_patterns` | string[] | `health, ping` | 忽略匹配的正则表达式（过滤已知/重复错误） |

#### 空闲检测机制

监控脚本通过文件修改时间判断 Agent 是否空闲：

1. 定期扫描 `cloud/`、`bridge/`、`frontend/src/` 目录下 `.py`、`.ts`、`.tsx`、`.js` 等文件的最后修改时间
2. 若最近一次修改距今超过 `idle_threshold_seconds`（默认 30 秒），判定 Agent 为空闲
3. Agent 空闲时才将错误写入通知文件；Agent 活跃时仅打印日志，不触发通知

#### Claude Code 定时任务设置

在 Claude Code 中设置定时任务，每 2 分钟检查错误通知文件：

```
/loop 2m 检查 .dus/log_errors.json 是否有新的错误通知，如有则分析并处理，处理完毕后清空 errors 数组
```

通知文件 `.dus/log_errors.json` 格式：

```json
{
  "errors": [
    {
      "source": "uvicorn.log",
      "line_no": 1234,
      "message": "ERROR: ...",
      "timestamp": "2026-05-11 14:30:00"
    }
  ],
  "last_updated": "2026-05-11 14:30:00"
}
```

---

## 技术栈

| 模块 | 技术 |
|------|------|
| **云端 API** | FastAPI + SQLAlchemy 2.0 (asyncio) + Pydantic |
| **数据库** | SQLite（开发）/ PostgreSQL（生产）|
| **终端 Bridge** | Python 3.12 + httpx + asyncio |
| **前端** | Next.js 16 (App Router) + React 19 + Tailwind CSS |
| **UI 组件** | shadcn/ui + TanStack Query |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Cloud API (FastAPI)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Machines │  │  Tasks   │  │  Issues  │  │ Projects │  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│         │            │            │                         │
│         └────────────┴────────────┘                         │
│                      SQLite / PostgreSQL                     │
└─────────────────────────────────────────────────────────────┘
           ▲                    ▲                    ▲
           │                    │                    │
    ┌──────┴──────┐      ┌──────┴──────┐      ┌──────┴──────┐
    │  Bridge #1  │      │  Bridge #2  │      │  Bridge #3  │
    │ mac-dev-01  │      │ mac-dev-02  │      │ linux-srv   │
    │ (多窗口)     │      │             │      │             │
    │ project-A   │      │             │      │             │
    │ project-B   │      │             │      │             │
    └─────────────┘      └─────────────┘      └─────────────┘
```

### 模块说明

| 模块 | 路径 | 说明 |
|------|------|------|
| `cloud/` | 云端 API | FastAPI 应用，提供设备注册、任务调度、项目管理接口 |
| `bridge/` | 终端代理 | 部署在每台设备上，负责从云端拉取任务并调用本地 Agent 执行，支持自动检测、取消、环境注入 |
| `frontend/` | 前端管理界面 | Next.js 应用，提供可视化操作界面 |

---

## 数据模型

### Machine（设备/终端）
| 字段 | 类型 | 说明 |
|------|------|------|
| `machine_id` | string | 设备唯一标识（如 `macbook-pro-office`） |
| `machine_name` | string | 展示名称 |
| `agent_type` | enum | Agent 类型：claude_code / openclaw / hermes_agent / codex |
| `agent_capability` | enum | 能力：remote_execution（远程执行）/ manual_only（仅提醒） |
| `agent_version` | string | Agent CLI 版本号（Bridge 启动时自动检测） |
| `status` | enum | 在线状态：online / offline |
| `is_enabled` | bool | 是否启用（禁用后不接收新任务） |
| `agent_status` | enum | Claude 状态：idle（空闲）/ busy（执行中）/ offline |
| `project_id` | uuid | 归属项目（自动领取时只领取该项目任务） |

### Task（任务）
| 字段 | 类型 | 说明 |
|------|------|------|
| `instruction` | string | 执行指令（核心字段） |
| `project_id` | uuid | 关联的项目 |
| `target_machine_id` | uuid | 指定的执行设备 |
| `issue_id` | uuid | 关联的 Issue |
| `status` | enum | 状态：pending / dispatched / running / completed / failed / cancelled / pending_manual |
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
| `idle_threshold_hours` | int | 空闲阈值（超时发送提醒） |

---

## API 概览

### 设备管理 `/api/v1/machines`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/machines` | 注册/更新设备 |
| GET | `/machines` | 设备列表 |
| GET | `/machines/dashboard` | 仪表盘数据（含运行中任务） |
| GET | `/machines/{uuid}` | 设备详情 |
| PATCH | `/machines/{uuid}` | 更新设备状态（启用/禁用） |
| GET | `/machines/{uuid}/poll` | 设备轮询任务（返回 `prior_session_id` / `prior_work_dir` 用于会话恢复）|

### 任务管理 `/api/v1/tasks`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建任务（支持关联 Issue） |
| GET | `/tasks` | 任务列表 |
| GET | `/tasks/{uuid}` | 任务详情 |
| PUT | `/tasks/{uuid}` | 更新任务状态 |
| POST | `/tasks/{uuid}/callback` | 设备回调上报结果（Hook，支持 session_id/work_dir） |
| POST | `/tasks/{uuid}/result` | Bridge 提交执行结果（支持 session_id/work_dir） |
| PUT | `/tasks/{uuid}/pin` | 运行时固定 session（崩溃恢复） |
| POST | `/tasks/{uuid}/remind` | 触发手动任务提醒（WeChat） |
| POST | `/tasks/{uuid}/claim` | 自动领取未分配任务 |

### Issue 管理 `/api/v1/issues`
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
| GET | `/projects` | 项目列表 |
| PUT | `/projects/{uuid}` | 更新项目 |

---

## 快速开始

### 1. 启动云端 API

```bash
cd cloud
pip install -r requirements.txt
cp .env.example .env  # 编辑 .env 填入配置
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端

```bash
cd frontend
npm install
cp .env.example .env.local  # 配置 API 地址和密钥
npm run dev
```

### 3. 部署 Bridge（方式一：手动）

```bash
cd bridge
pip install -r requirements.txt
cp config.yaml.example config.yaml  # 编辑 config.yaml
python -m bridge.main
```

**配置说明**：`agent.path` 支持三种解析方式（优先级从高到低）：
1. 环境变量（如 `DUS_CLAUDE_PATH=/usr/local/bin/claude`）
2. `config.yaml` 中显式配置的路径
3. 系统 PATH 自动搜索（默认二进制名：`claude`、`codex`、`hermes`、`openclaw`）

**环境变量**：Agent 执行时自动注入以下变量：
- `DUS_TOKEN` — Cloud API Key
- `DUS_API_URL` — Cloud API 地址
- `DUS_MACHINE_ID` — 当前机器 ID
- `DUS_TASK_ID` — 当前任务 ID
- `DUS_MACHINE_UUID` — 持久化机器 UUID

**健康检查**：启动后访问 http://127.0.0.1:19514/health 查看状态；`POST /shutdown` 触发优雅关闭

**工作空间清理**：任务完成后自动写入 `.gc_meta.json`，GC 按 `gc.interval` 周期扫描并删除超时的旧工作目录

### 3. 部署 Bridge（方式二：一键安装，推荐）

在项目目录下下载并运行一键安装脚本：

```bash
cd ~/projects/my-ai-project
curl -sLo dus-setup.sh https://raw.githubusercontent.com/pwyyeye/dus/main/bridge/dus-setup.sh
chmod +x dus-setup.sh
./dus-setup.sh --auto
```

脚本会自动完成：
1. 检查并安装 Python 依赖
2. 生成配置文件（基于项目路径生成 project_id）
3. 启动 Bridge

### 4. 访问管理界面

打开 [http://localhost:3000](http://localhost:3000)

---

## 近期更新记录

### 2026-05-08

**Issue-Task 分层模型 + Session Resumption（Multica 设计迁移）**
- **Issue 工作单元**：新增 `Issue` 模型作为工作项管理层，支持标题、描述、状态、优先级、负责人
- **Task 执行单元**：`Task` 新增 `issue_id`、`session_id`、`work_dir` 字段，一个 Issue 可包含多个 Task 形成执行历史
- **自动派发**：创建 Issue 并分配给机器时，自动创建关联 Task；更新分配时自动取消旧 Task、创建新 Task
- **Session Resumption（会话恢复）**：
  - 任务完成后 Bridge 提交 `session_id` + `work_dir` 回 Cloud
  - 同一 Issue 产生新 Task 时，Cloud 在 poll 响应中返回 `prior_session_id` + `prior_work_dir`
  - Bridge 使用 `--resume <session_id>` 恢复 Claude Code 对话上下文，使用 `prior_work_dir` 保持工作目录连续性
  - 新增 `PUT /tasks/{uuid}/pin` 接口支持运行中固定 session（崩溃恢复）
- **前端 Issue 管理页面**：新增 Issue 列表页（支持状态筛选、新建弹窗）和 Issue 详情页（含执行历史任务表格）

**Bridge Agent CLI 自动检测与执行升级（Multica 设计迁移）**
- **Agent CLI 自动检测**：Bridge 启动时按优先级自动解析 Agent 可执行文件路径
  1. 环境变量覆盖（如 `DUS_CLAUDE_PATH`）
  2. 配置文件中的 `agent.path`
  3. 系统 PATH 自动搜索（`shutil.which`）
- **Claude Code 非交互式自动执行**：引入 `--permission-mode bypassPermissions` 标志，使 Claude Code 在远程执行时自动批准所有工具调用（文件编辑、bash 命令等），无需人工交互
- **Agent 版本检测**：Bridge 启动时自动运行 `claude --version` 并记录版本号
- **环境变量注入**：执行 Agent 时自动注入 `DUS_TOKEN`、`DUS_API_URL`、`DUS_MACHINE_ID`、`DUS_TASK_ID`，供 Agent 内部逻辑使用
- **任务取消机制**：Bridge 在任务执行期间每 5 秒轮询云端任务状态，若检测到 `cancelled` 状态则立即终止 Agent 进程

**Bridge 部署与运维增强（Multica 部署优势整合）**
- **本地健康检查 HTTP 服务**：Bridge 启动时在 `127.0.0.1:19514` 监听健康端口
  - `GET /health` 返回运行状态、PID、运行时间、活跃任务数、Agent 版本
  - `POST /shutdown` 触发优雅关闭（不依赖 OS 信号，Windows 友好）
  - 端口占用检测：若端口已被占用则拒绝启动，防止重复运行多个 Bridge 实例
- **持久化机器 UUID**：在 `~/.dus/machine.uuid` 中持久化存储机器唯一标识
  - 不因 hostname 变化或配置修改而重复注册为新机器
  - 原子写入 + 0600 权限，损坏时自动重新生成
- **工作空间垃圾回收**：定时清理已完成/失败/取消的任务工作目录
  - 活跃任务保护：正在运行中的任务目录不会被清理
  - 配置项：`gc.enabled`、`gc.interval`（扫描间隔）、`gc.ttl`（保留时长）
  - 任务完成后写入 `.gc_meta.json` 元数据，用于精确 TTL 判断
- **并发数配置化**：`max_concurrent_tasks` 从硬编码改为配置项（默认 3）
- **API Client 身份头部**：所有请求携带 `X-Client-Platform`、`X-Client-OS` 头部，便于云端调试和版本统计

### 2026-04-20

**首页仪表盘重构**
- 改为卡片式布局展示所有设备
- 每个设备卡片显示：在线状态、可用性、运行中任务、今日完成数
- 支持点击设备卡片快捷下发任务
- 点击"启用/禁用"按钮管理设备可用性

**设备管理增强**
- 新增 `is_enabled` 字段控制设备是否可用
- 设备状态分为两个维度：在线状态（online/offline）+ 可用性（enabled/disabled）
- 新增 `PATCH /machines/{uuid}` 接口更新设备状态

**任务模型精简**
- 核心字段：`instruction`（指令）+ `project_id`（项目）+ `target_machine_id`（设备）
- 移除：`title`、`description`、`priority`、`deadline`、`timeout_seconds`
- 保留：`result`（执行结果）、`error_message`（错误信息）

**多窗口任务分发**
- `GET /machines/{uuid}/poll` 新增 `project_id` 查询参数
- Bridge 可按项目 ID 过滤，只拉取该项目的任务
- 支持同一设备运行多个 Claude Code 窗口，每个窗口处理不同项目

**任务回调接口**
- 新增 `POST /tasks/{uuid}/callback` 接口
- 设备执行完成后可通过 Hook 脚本调用，回上报执行结果
- Body 格式：`{exit_code, stdout, stderr, error_type}`

**项目自动创建**
- Bridge 注册时可通过 `project_id` 指定关联项目
- 云端自动创建不存在的项目
- 无需预先在云端创建项目，Bridge 上报时自动注册

**自动领取项目隔离**
- Machine 绑定 `project_id`，自动领取和手动 claim 时只领取自己项目的任务
- Bridge 轮询时服务端强制使用机器绑定的项目，不再依赖客户端传入参数
- 跨项目领取返回 403 拒绝

**一键安装 Bridge**
- `bridge/dus-setup.sh` 一键安装脚本
- 在项目目录下运行，自动完成依赖安装、配置生成、Bridge 启动
- 支持多项目：每个项目目录独立运行 Bridge 实例
- 使用 `project_id` 区分任务归属

**终端 Claude 状态监控**
- Bridge 定时上报 Claude Code 运行状态（idle / busy / offline）
- `PATCH /machines/{uuid}` 接口支持更新 `agent_status`
- 前端可实时显示终端 Claude 是否正在执行任务

---

## 项目结构

```
DUS/
├── cloud/                    # 云端 API (FastAPI)
│   ├── main.py              # 应用入口
│   ├── models.py            # 数据模型
│   ├── schemas.py           # Pydantic 模型
│   ├── routers/             # API 路由
│   │   ├── machines.py     # 设备管理
│   │   ├── tasks.py        # 任务管理
│   │   ├── issues.py       # Issue 管理
│   │   └── projects.py      # 项目管理
│   └── dus.db              # SQLite 数据库
│
├── bridge/                   # 终端代理
│   ├── bridge/
│   │   ├── main.py         # Bridge 主程序
│   │   ├── api_client.py  # 云端 API 客户端
│   │   ├── executor.py     # Agent 执行器
│   │   ├── config.py       # 配置管理
│   │   ├── health.py       # 本地健康检查 HTTP 服务
│   │   ├── gc.py           # 工作空间垃圾回收
│   │   └── identity.py     # 持久化机器 UUID
│   ├── config.yaml.example # 配置示例
│   └── dus-setup.sh        # 一键安装脚本
│
├── scripts/
│   └── log_monitor.py      # 后端日志监控脚本
│
├── .dus/
│   ├── log_monitor.json    # 日志监控配置
│   ├── log_errors.json     # 错误通知文件（监控脚本写入，Claude Code 读取）
│   └── log_monitor_state.json # 监控状态（文件位置、已报告哈希）
│
└── frontend/                 # 前端管理界面 (Next.js)
    ├── src/app/            # 页面
    │   ├── page.tsx        # 首页仪表盘
    │   ├── machines/       # 设备管理
    │   ├── tasks/         # 任务管理
    │   ├── issues/        # Issue 管理
    │   └── projects/      # 项目管理
    ├── src/components/     # UI 组件
    └── src/lib/api.ts     # API 客户端
```

---

## License

Internal use only.
