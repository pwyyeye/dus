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

## 技术栈

| 模块                  | 技术                                              |
| --------------------- | ------------------------------------------------- |
| **云端 API**    | FastAPI + SQLAlchemy 2.0 (asyncio) + Pydantic     |
| **数据库**      | SQLite（开发）/ PostgreSQL（生产）                |
| **终端 Bridge** | Python 3.12 + httpx + asyncio                     |
| **前端**        | Next.js 16 (App Router) + React 19 + Tailwind CSS |
| **UI 组件**     | shadcn/ui + TanStack Query                        |

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

| 模块          | 路径         | 说明                                                                                    |
| ------------- | ------------ | --------------------------------------------------------------------------------------- |
| `cloud/`    | 云端 API     | FastAPI 应用，提供设备注册、任务调度、项目管理接口                                      |
| `bridge/`   | 终端代理     | 部署在每台设备上，负责从云端拉取任务并调用本地 Agent 执行，支持自动检测、取消、环境注入 |
| `frontend/` | 前端管理界面 | Next.js 应用，提供可视化操作界面                                                        |

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

### 3. 部署 Bridge

**Windows 一键安装**（推荐）：

```powershell
irm https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.ps1 | iex
```

安装后，在项目目录下运行 `dus setup` 进行配置：

```powershell
cd ~\your-project
dus setup        # 交互式配置
dus setup --auto # 自动配置
```

管理命令：

- `dus start` — 启动 Bridge
- `dus stop` — 停止 Bridge
- `dus restart` — 重启 Bridge
- `dus status` — 查看状态

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

### 4. 访问管理界面

打开 [http://localhost:3000](http://localhost:3000)

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
│
├── scripts/
│   ├── install.ps1        # Windows 一键安装脚本
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
