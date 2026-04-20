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
│   └── logger.py        # 日志配置
├── config.yaml.example  # 配置模板
├── dus-setup.sh        # 一键安装脚本
└── requirements.txt
```

## 快速开始

### 方式一：一键安装（推荐）

在项目目录下下载并运行一键安装脚本：

```bash
cd ~/projects/my-ai-project
curl -sLo dus-setup.sh https://raw.githubusercontent.com/pwyyeye/dus/main/bridge/dus-setup.sh
chmod +x dus-setup.sh
./dus-setup.sh --auto
```

脚本会自动：
1. 检查依赖（Python、pip、httpx、loguru、pyyaml）
2. 生成配置文件（项目 ID、设备 ID 等）
3. 安装 Python 依赖
4. 启动 Bridge

> 注意：`curl | bash` 方式无法传递参数，请先下载脚本再运行

### 方式二：手动安装

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp config.yaml.example config.yaml
# 编辑 config.yaml

# 3. 运行
python -m bridge.main
```

## 配置说明

### config.yaml 字段说明

| 字段 | 说明 |
|------|------|
| `machine.machine_id` | 机器唯一标识（如 `mac-mini-lab`） |
| `machine.machine_name` | 展示名称 |
| `machine.agent_type` | Agent 类型：`claude_code` / `openclaw` / `hermes_agent` / `codex` / `windsurf` |
| `machine.agent_capability` | 能力：`remote_execution`（远程执行）或 `manual_only`（仅提醒） |
| `machine.project_id` | 关联的项目 ID（可选，不填则不关联项目） |
| `cloud.api_url` | 云端 API 地址 |
| `cloud.api_key` | API 认证密钥 |
| `cloud.poll_interval` | 轮询间隔（秒） |
| `agent.path` | Agent 可执行文件路径 |
| `agent.timeout` | 任务超时时间（秒） |

### dus-setup.sh 使用方式

```bash
./dus-setup.sh              # 交互式安装
./dus-setup.sh --auto       # 自动安装（需要设置 DUS_API_KEY 环境变量）
./dus-setup.sh --status     # 查看状态
./dus-setup.sh --restart    # 重启 Bridge
./dus-setup.sh --stop       # 停止 Bridge
./dus-setup.sh --uninstall  # 卸载
```

## 多项目支持

同一台设备可以运行多个 Bridge 实例，每个项目目录独立运行：

```bash
# 项目 A 的 Bridge
cd ~/projects/project-A
./dus-setup.sh

# 项目 B 的 Bridge
cd ~/projects/project-B
./dus-setup.sh
```

每个 Bridge 通过 `project_id` 区分任务归属，轮询时只拉取该项目的任务。

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
| OpenClaw | `openclaw` | 占位（待验证 CLI） |
| Hermes Agent | `hermes_agent` | 占位（待验证 CLI） |
| Codex | `codex` | 占位（待验证 CLI） |
| Windsurf | `windsurf` | 占位（待验证 CLI） |

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
