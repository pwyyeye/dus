# DUS Bridge

分布式AI终端统一调度系统 - 终端代理

部署在每台 AI 终端机器上，负责从云端拉取任务并调用本地 Agent 执行。

## 技术栈

- **Python 3.10+** - 运行环境
- **httpx** - 异步 HTTP 客户端
- **loguru** - 日志
- **PyYAML** - 配置文件

## 项目结构

```
bridge/
├── bridge/
│   ├── main.py          # 主入口，Bridge 类
│   ├── config.py        # 配置加载
│   ├── api_client.py    # 云端 API 客户端
│   ├── executor.py      # Agent 执行器
│   ├── health.py        # 健康检查服务
│   ├── gc.py            # 任务垃圾回收
│   ├── identity.py      # 机器身份持久化
│   └── logger.py        # 日志配置
├── config.yaml.example  # 配置模板
├── dus-setup.sh         # macOS/Linux 项目级管理脚本
├── dus-setup.ps1        # Windows 项目级管理脚本
└── requirements.txt
```

## 快速开始

### 方式一：一键安装全局 CLI（推荐）

全局安装 `dus` 命令，所有项目共用一份 bridge 代码：

**macOS / Linux：**

```bash
curl -fsSL https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.sh | bash
```

**Windows（PowerShell）：**

```powershell
irm https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.ps1 | iex
```

装完验证：

```bash
dus --help
```

### 方式二：项目目录直接运行

不需要全局安装，直接在项目目录下载脚本运行：

**macOS / Linux：**

```bash
cd ~/projects/my-ai-project
DUS_MODE=auto curl -fsSL https://raw.githubusercontent.com/pwyyeye/dus/main/bridge/dus-setup.sh | bash
```

**Windows（PowerShell）：**

```powershell
cd ~\projects\my-ai-project
$env:DUS_MODE="auto"
irm https://raw.githubusercontent.com/pwyyeye/dus/main/bridge/dus-setup.ps1 | iex
```

> `DUS_MODE=auto` 会自动生成配置并启动 Bridge。你也可以先去掉它进行交互式配置。

---

## dus CLI 使用指南

全局安装后，在项目目录使用 `dus` 命令管理 Bridge：

```bash
cd ~/projects/my-ai-project

# 初始化配置（交互式）
dus setup

# 自动配置
dus setup --auto

# 启动 Bridge
dus start

# 查看状态
dus status

# 重启 Bridge
dus restart

# 停止 Bridge
dus stop
```

### dus setup 流程

`dus setup` 会：

1. 检查依赖（Python、pip、httpx、loguru、pyyaml）
2. 生成项目级配置到 `.dus/config.yaml`
3. 启动 Bridge 守护进程

配置按项目隔离，每个项目目录有自己的 `.dus/` 文件夹：

```
~/projects/my-ai-project/
├── .dus/
│   ├── config.yaml      # 项目专属配置
│   ├── bridge.pid       # 进程 PID
│   ├── bridge.log       # 运行日志
│   └── tasks/           # 任务工作目录
└── src/...
```

### 环境变量

| 变量 | 说明 |
|------|------|
| `DUS_MODE` | `auto` / `stop` / `restart` / `status`，用于 `curl \| bash` 模式 |
| `DUS_API_KEY` | 自动模式下的 API Key |
| `DUS_API_URL` | 自动模式下的 API URL（默认 `http://localhost:8000/api/v1`） |
| `DUS_INSTALL_DIR` | 全局安装目录（默认 `~/.dus`） |

---

## 配置说明

### config.yaml 字段说明

| 字段 | 说明 |
|------|------|
| `machine.machine_id` | 机器唯一标识（如 `mac-mini-lab`） |
| `machine.machine_name` | 展示名称 |
| `machine.agent_type` | Agent 类型：`claude_code` / `openclaw` / `hermes_agent` / `codex` |
| `machine.agent_capability` | 能力：`remote_execution`（远程执行）或 `manual_only`（仅提醒） |
| `machine.project_id` | 关联的项目 ID（自动领取/claim 时限定项目范围） |
| `cloud.api_url` | 云端 API 地址 |
| `cloud.api_key` | API 认证密钥 |
| `cloud.poll_interval` | 轮询间隔（秒） |
| `agent.path` | Agent 可执行文件路径 |
| `agent.timeout` | 任务超时时间（秒） |
| `health.port` | 本地 HTTP 健康检查端口（默认 `19514`，`0` 禁用） |
| `gc.enabled` | 是否启用任务目录垃圾回收 |
| `gc.interval` | GC 扫描间隔（秒） |
| `gc.ttl` | 删除超过此时间的任务目录（秒） |
| `max_concurrent_tasks` | 最大并发任务数 |

---

## 多项目支持

同一台设备可以运行多个 Bridge 实例，每个项目目录独立运行：

```bash
# 项目 A
cd ~/projects/project-A
dus setup --auto

# 项目 B
cd ~/projects/project-B
dus setup --auto
```

每个 Bridge 通过 `project_id` 区分任务归属，轮询时只拉取该项目的任务。

---

## 工作流程

1. **注册** - 启动时向云端注册本机（machine_id、agent_type、project_id 等）
2. **自动创建项目** - 如果 `project_id` 对应的项目不存在，云端自动创建
3. **轮询** - 每 `poll_interval` 秒向云端 `/machines/{uuid}/poll` 拉取待执行任务
4. **执行** - 对 `remote_execution` 任务，调用本地 Agent 执行
5. **结果上报** - 任务完成后调用 `/tasks/{uuid}/callback` 提交结果

## 支持的 Agent

| Agent | 类型 | 状态 |
|-------|------|------|
| Claude Code | `claude_code` | 已实现 |
| OpenClaw | `openclaw` | 已实现（Generic 模式） |
| Hermes Agent | `hermes_agent` | 已实现（Generic 模式） |
| Codex | `codex` | 已实现（--print 模式） |

---

## 手动安装（开发者）

```bash
# 1. 克隆代码
git clone https://github.com/pwyyeye/dus.git
cd dus/bridge

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp config.yaml.example config.yaml
# 编辑 config.yaml，填写 machine_id, api_url, api_key

# 4. 运行
python -m bridge.main
```

---

## macOS 自动启动 (launchd)

将 Bridge 配置为 macOS 系统服务，开机自动启动。

### 1. 创建 plist 文件

```bash
mkdir -p ~/Library/LaunchAgents
cp com.dus.bridge.plist ~/Library/LaunchAgents/
```

### 2. 编辑配置

修改 `com.dus.bridge.plist` 中的路径和参数：
- `WorkingDirectory`: 项目目录
- `EnvironmentVariables`: 设置 `PYTHONPATH`
- `ProgramArguments`: Python 解释器和 bridge 模块路径

### 3. 加载服务

```bash
# 加载服务（开机自启）
launchctl load ~/Library/LaunchAgents/com.dus.bridge.plist

# 立即启动
launchctl start com.dus.bridge

# 查看状态
launchctl list | grep dus

# 停止服务
launchctl stop com.dus.bridge

# 卸载服务
launchctl unload ~/Library/LaunchAgents/com.dus.bridge.plist
```

---

## Linux 自动启动 (systemd)

将 Bridge 配置为 systemd 用户服务，开机自动启动。

### 1. 创建服务文件

```bash
mkdir -p ~/.config/systemd/user
cp dus-bridge.service ~/.config/systemd/user/
```

### 2. 编辑配置

修改 `dus-bridge.service` 中的路径和参数：
- `WorkingDirectory`: 项目目录
- `Environment`: 设置 `PYTHONPATH`
- `ExecStart`: Python 解释器和 bridge 模块路径

### 3. 启用服务

```bash
# 重新加载 systemd
systemctl --user daemon-reload

# 启用服务（开机自启）
systemctl --user enable dus-bridge

# 立即启动
systemctl --user start dus-bridge

# 查看状态
systemctl --user status dus-bridge

# 停止服务
systemctl --user stop dus-bridge

# 重启服务
systemctl --user restart dus-bridge
```

---

## 日志

Bridge 日志默认输出到 `.dus/bridge.log`：

```
2026-04-20 12:00:00 | INFO     | bridge.main - Bridge starting — machine_id=mac-mini-lab, agent_type=claude_code, capability=remote_execution
2026-04-20 12:00:01 | INFO     | bridge.api_client - Registered machine: mac-mini-lab (uuid=...)
2026-04-20 12:00:05 | INFO     | bridge.main - Polling every 30s ...
2026-04-20 12:00:10 | INFO     | bridge.api_client - Polled 2 task(s)
```

## License

Internal use only.
