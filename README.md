# DUS - 分布式AI终端统一调度系统

> **Distributed AI Terminal Unified Scheduling System**

一个用于统一管理和调度多台终端设备上 AI Agent（如 Claude Code）执行任务的管理平台。

---

## 核心功能

### 设备管理
- **设备注册与状态监控**：终端设备（Bridge）启动时自动注册，心跳维持在线状态
- **设备可用性控制**：支持启用/禁用设备，被禁用的设备不会收到新任务
- **多窗口支持**：同一设备可运行多个 Claude Code 窗口，每个窗口通过 `project_id` 拉取属于自己的任务

### 任务调度
- **指令下发**：向指定设备下发执行指令（Instruction）
- **项目绑定**：任务与项目（Project）绑定，不同项目可分配给不同设备
- **状态跟踪**：完整任务状态流转（pending → dispatched → running → completed/failed）
- **结果回调**：设备执行完成后通过 Hook 脚本回调上报结果（exit_code, stdout, stderr）

### 前端管理
- **首页设备仪表盘**：卡片式展示所有设备状态、运行中任务，一键下发任务
- **设备管理**：查看设备列表、在线状态、Agent 类型
- **任务管理**：查看/创建任务，追踪执行状态
- **项目管理**：查看/创建项目，关联任务

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
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Machines │  │  Tasks   │  │ Projects │                  │
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
| `bridge/` | 终端代理 | 部署在每台设备上，负责从云端拉取任务并调用本地 Agent 执行 |
| `frontend/` | 前端管理界面 | Next.js 应用，提供可视化操作界面 |

---

## 数据模型

### Machine（设备/终端）
| 字段 | 类型 | 说明 |
|------|------|------|
| `machine_id` | string | 设备唯一标识（如 `macbook-pro-office`） |
| `machine_name` | string | 展示名称 |
| `agent_type` | enum | Agent 类型：claude_code / openclaw / hermes_agent / codex / windsurf |
| `agent_capability` | enum | 能力：remote_execution（远程执行）/ manual_only（仅提醒） |
| `status` | enum | 在线状态：online / offline |
| `is_enabled` | bool | 是否启用（禁用后不接收新任务） |

### Task（任务）
| 字段 | 类型 | 说明 |
|------|------|------|
| `instruction` | string | 执行指令（核心字段） |
| `project_id` | uuid | 关联的项目 |
| `target_machine_id` | uuid | 指定的执行设备 |
| `status` | enum | 状态：pending / dispatched / running / completed / failed / cancelled |
| `result` | json | 执行结果：{exit_code, stdout, stderr, error_type} |
| `error_message` | string | 错误信息 |

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
| GET | `/machines/{uuid}/poll` | 设备轮询任务（支持 `?project_id=` 按项目过滤）|

### 任务管理 `/api/v1/tasks`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建任务 |
| GET | `/tasks` | 任务列表 |
| GET | `/tasks/{uuid}` | 任务详情 |
| PUT | `/tasks/{uuid}` | 更新任务状态 |
| POST | `/tasks/{uuid}/callback` | 设备回调上报结果（Hook） |
| POST | `/tasks/{uuid}/result` | Bridge 提交执行结果 |

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

### 3. 部署 Bridge（方式二：一键安装，推荐）

在项目目录下运行一键安装脚本：

```bash
cd ~/projects/my-ai-project
curl -sL https://raw.githubusercontent.com/your-org/dus/main/bridge/dus-setup.sh | bash
# 或下载脚本后直接运行
./dus-setup.sh
```

脚本会自动完成：
1. 检查并安装 Python 依赖
2. 生成配置文件（基于项目路径生成 project_id）
3. 启动 Bridge

### 4. 访问管理界面

打开 [http://localhost:3000](http://localhost:3000)

---

## 近期更新记录

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

**一键安装 Bridge**
- `bridge/dus-setup.sh` 一键安装脚本
- 在项目目录下运行，自动完成依赖安装、配置生成、Bridge 启动
- 支持多项目：每个项目目录独立运行 Bridge 实例
- 使用 `project_id` 区分任务归属

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
│   │   └── projects.py      # 项目管理
│   └── dus.db              # SQLite 数据库
│
├── bridge/                   # 终端代理
│   ├── bridge/
│   │   ├── main.py         # Bridge 主程序
│   │   ├── api_client.py  # 云端 API 客户端
│   │   ├── executor.py     # Agent 执行器
│   │   └── config.py       # 配置管理
│   ├── config.yaml.example # 配置示例
│   └── dus-setup.sh        # 一键安装脚本
│
└── frontend/                 # 前端管理界面 (Next.js)
    ├── src/app/            # 页面
    │   ├── page.tsx        # 首页仪表盘
    │   ├── machines/       # 设备管理
    │   ├── tasks/         # 任务管理
    │   └── projects/      # 项目管理
    ├── src/components/     # UI 组件
    └── src/lib/api.ts     # API 客户端
```

---

## License

Internal use only.
