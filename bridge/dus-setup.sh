#!/bin/bash
# =============================================================================
# DUS Bridge 项目级管理脚本
#
# 此脚本由全局 install.sh 安装到 ~/.dus/bridge/bridge/dus-setup.sh
# 可通过 dus CLI 调用，也可在项目目录直接运行。
#
# 使用方式:
#   ./dus-setup.sh              # 交互式安装
#   ./dus-setup.sh --auto       # 自动使用默认配置
#   ./dus-setup.sh --start      # 启动 Bridge
#   ./dus-setup.sh --stop       # 停止 Bridge
#   ./dus-setup.sh --restart    # 重启 Bridge
#   ./dus-setup.sh --status     # 查看状态
#   ./dus-setup.sh --uninstall  # 卸载 Bridge
#
# 环境变量（支持 curl | bash 模式）:
#   DUS_MODE=auto|stop|restart|status  等效于 --auto, --stop 等参数
#   DUS_API_KEY                        自动模式下的 API Key
#   DUS_API_URL                        自动模式下的 API URL
# =============================================================================

set -e

# ---------------------------------------------------------------------------
# 颜色与输出
# ---------------------------------------------------------------------------
if [ -t 1 ] || [ -t 2 ]; then
  BOLD='\033[1m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  RED='\033[0;31m'
  CYAN='\033[0;36m'
  RESET='\033[0m'
else
  BOLD='' GREEN='' YELLOW='' RED='' CYAN='' RESET=''
fi

info()  { printf "${BOLD}${CYAN}==> %s${RESET}\n" "$*"; }
ok()    { printf "${BOLD}${GREEN}✓ %s${RESET}\n" "$*"; }
warn()  { printf "${BOLD}${YELLOW}⚠ %s${RESET}\n" "$*" >&2; }
fail()  { printf "${BOLD}${RED}✗ %s${RESET}\n" "$*" >&2; }

log_info()  { echo -e "${GREEN}[INFO]${RESET} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET} $1"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $1"; }

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 如果脚本在全局安装目录运行（通过 dus CLI 调用），使用当前工作目录作为项目目录
GLOBAL_INSTALL_DIR="${DUS_INSTALL_DIR:-$HOME/.dus}/bridge"
if [[ "$SCRIPT_DIR" == "$GLOBAL_INSTALL_DIR"* ]]; then
    PROJECT_ROOT="$(pwd)"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

DUS_DIR="$PROJECT_ROOT/.dus"

CONFIG_FILE="$DUS_DIR/config.yaml"
PID_FILE="$DUS_DIR/bridge.pid"
LOG_FILE="$DUS_DIR/bridge.log"

DEFAULT_API_URL="http://localhost:8000/api/v1"
DEFAULT_POLL_INTERVAL=30
DEFAULT_TIMEOUT=7200
DEFAULT_LOG_LEVEL="INFO"

# 全局 bridge 代码目录（由 install.sh 安装）
GLOBAL_BRIDGE_DIR="${DUS_INSTALL_DIR:-$HOME/.dus}/bridge"

# 确定使用哪个 bridge 目录
resolve_bridge_dir() {
    if [ -d "$PROJECT_ROOT/bridge/bridge" ]; then
        echo "$PROJECT_ROOT/bridge"
    elif [ -d "$GLOBAL_BRIDGE_DIR/bridge" ]; then
        echo "$GLOBAL_BRIDGE_DIR"
    elif [ -d "$PROJECT_ROOT/../bridge/bridge" ]; then
        echo "$PROJECT_ROOT/../bridge"
    else
        echo ""
    fi
}

BRIDGE_DIR="$(resolve_bridge_dir)"
PYTHONPATH_DIR="${BRIDGE_DIR:-$PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# 帮助信息
# ---------------------------------------------------------------------------
show_help() {
    cat << EOF
${BOLD}DUS Bridge 项目级管理脚本${RESET}

用法: dus-setup.sh [选项]

选项:
    --auto       自动使用默认配置（不提示输入）
    --start      启动 Bridge
    --stop       停止 Bridge
    --restart    重启 Bridge
    --status     查看 Bridge 状态
    --uninstall  卸载 Bridge（删除 .dus 目录）
    -h, --help   显示帮助信息

环境变量（支持 curl | bash 模式）:
    DUS_MODE=auto|stop|restart|status  等效于对应参数
    DUS_API_KEY                        自动模式下的 API Key
    DUS_API_URL                        自动模式下的 API URL

示例:
    DUS_MODE=auto curl -fsSL ... | bash    # 一键自动安装
    ./dus-setup.sh                         # 交互式安装
    ./dus-setup.sh --auto                  # 自动安装
    ./dus-setup.sh --stop                  # 停止 Bridge
EOF
}

# ---------------------------------------------------------------------------
# 检查依赖
# ---------------------------------------------------------------------------
check_dependencies() {
    info "检查依赖..."

    if ! command -v python3 &> /dev/null; then
        fail "Python3 未安装，请先安装 Python 3.10+"
    fi

    if ! python3 -m pip --version &> /dev/null; then
        fail "pip 未安装，请先安装 pip"
    fi

    # 尝试导入必需包，缺失则安装
    local missing=()
    python3 -c "import httpx" 2>/dev/null || missing+=(httpx)
    python3 -c "import loguru" 2>/dev/null || missing+=(loguru)
    python3 -c "import yaml" 2>/dev/null || missing+=(pyyaml)

    if [ ${#missing[@]} -gt 0 ]; then
        log_warn "缺少 Python 包: ${missing[*]}，正在安装..."
        python3 -m pip install --user --break-system-packages "${missing[@]}" 2>/dev/null || \
            python3 -m pip install --user "${missing[@]}"
    fi

    # 查找 Claude CLI
    CLAUDE_PATH=""
    if command -v claude &> /dev/null; then
        CLAUDE_PATH=$(which claude)
    elif [ -f "/usr/local/bin/claude" ]; then
        CLAUDE_PATH="/usr/local/bin/claude"
    elif [ -f "$HOME/.claude/bin/claude" ]; then
        CLAUDE_PATH="$HOME/.claude/bin/claude"
    fi

    if [ -z "$CLAUDE_PATH" ]; then
        log_warn "未找到 claude 命令，请确保已安装 Claude Code"
        CLAUDE_PATH="claude"
    fi

    ok "依赖检查完成"
}

# ---------------------------------------------------------------------------
# 生成项目/设备 ID
# ---------------------------------------------------------------------------
generate_project_id() {
    echo "proj-$(echo -n "$PROJECT_ROOT" | md5sum | cut -c1-8)"
}

generate_machine_id() {
    local project_suffix=$(echo -n "$PROJECT_ROOT" | md5sum | cut -c1-4)
    echo "dev-$(hostname)-${project_suffix}"
}

# ---------------------------------------------------------------------------
# 交互式配置
# ---------------------------------------------------------------------------
interactive_config() {
    echo ""
    echo "${BOLD}=== DUS Bridge 安装配置 ===${RESET}"
    echo ""
    echo "  项目目录: $PROJECT_ROOT"
    echo "  项目 ID:  $PROJECT_ID"
    echo ""

    read -p "云端 API URL [$DEFAULT_API_URL]: " API_URL
    API_URL=${API_URL:-$DEFAULT_API_URL}

    read -p "API Key: " API_KEY
    while [ -z "$API_KEY" ]; do
        log_error "API Key 不能为空"
        read -p "API Key: " API_KEY
    done

    DEFAULT_MACHINE_NAME="$(hostname) - $(basename "$PROJECT_ROOT")"
    read -p "设备名称 [$DEFAULT_MACHINE_NAME]: " MACHINE_NAME
    MACHINE_NAME=${MACHINE_NAME:-$DEFAULT_MACHINE_NAME}

    read -p "轮询间隔(秒) [$DEFAULT_POLL_INTERVAL]: " POLL_INTERVAL
    POLL_INTERVAL=${POLL_INTERVAL:-$DEFAULT_POLL_INTERVAL}

    read -p "任务超时时间(秒) [$DEFAULT_TIMEOUT]: " TIMEOUT
    TIMEOUT=${TIMEOUT:-$DEFAULT_TIMEOUT}

    read -p "Claude 路径 [$CLAUDE_PATH]: " CLAUDE_PATH_INPUT
    CLAUDE_PATH=${CLAUDE_PATH_INPUT:-$CLAUDE_PATH}

    echo ""
    echo "${BOLD}=== 配置摘要 ===${RESET}"
    echo "  项目 ID:      $PROJECT_ID"
    echo "  设备 ID:      $MACHINE_ID"
    echo "  设备名称:     $MACHINE_NAME"
    echo "  API URL:      $API_URL"
    echo "  轮询间隔:     ${POLL_INTERVAL}秒"
    echo "  任务超时:     ${TIMEOUT}秒"
    echo "  Claude 路径:   $CLAUDE_PATH"
    echo ""

    read -p "确认配置正确? (Y/n): " confirm
    confirm=${confirm:-Y}
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "安装已取消"
        exit 0
    fi
}

# ---------------------------------------------------------------------------
# 自动配置
# ---------------------------------------------------------------------------
auto_config() {
    info "使用自动配置模式..."

    API_URL="${DUS_API_URL:-$DEFAULT_API_URL}"
    if [ -n "${DUS_API_KEY:-}" ]; then
        API_KEY="$DUS_API_KEY"
    else
        API_KEY="$(openssl rand -hex 16 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -1)"
        log_info "自动生成 API Key: $API_KEY"
        log_info "请在 Cloud 端配置相同的 Key 以便验证"
    fi

    MACHINE_NAME="$(hostname) - $(basename "$PROJECT_ROOT")"
    POLL_INTERVAL="$DEFAULT_POLL_INTERVAL"
    TIMEOUT="$DEFAULT_TIMEOUT"

    # 如果当前项目没有 bridge 代码，尝试使用全局的
    if [ -z "$BRIDGE_DIR" ]; then
        log_warn "未找到 bridge 代码，尝试从 GitHub 下载..."
        cd "$PROJECT_ROOT"
        curl -sL "https://github.com/pwyyeye/dus/archive/refs/heads/main.zip" -o dus-main.zip
        set +e
        yes | unzip -o dus-main.zip >/dev/null 2>&1
        set -e
        if [ -d "dus-main/bridge" ]; then
            cp -r dus-main/bridge "$PROJECT_ROOT/bridge"
        fi
        rm -rf dus-main dus-main.zip
        BRIDGE_DIR="$(resolve_bridge_dir)"
        PYTHONPATH_DIR="${BRIDGE_DIR:-$PROJECT_ROOT}"
    fi

    ok "配置完成"
}

# ---------------------------------------------------------------------------
# 生成配置文件
# ---------------------------------------------------------------------------
generate_config() {
    info "生成配置文件: $CONFIG_FILE"

    mkdir -p "$DUS_DIR"

    cat > "$CONFIG_FILE" << EOF
version: "1.0.0"

machine:
  machine_id: "$MACHINE_ID"
  machine_name: "$MACHINE_NAME"
  agent_capability: "remote_execution"
  project_id: "$PROJECT_ID"

cloud:
  api_url: "$API_URL"
  api_key: "$API_KEY"
  poll_interval: $POLL_INTERVAL

agent:
  path: "$CLAUDE_PATH"
  workdir_template: "$DUS_DIR/tasks/{task_id}"
  timeout: $TIMEOUT

logging:
  level: "$DEFAULT_LOG_LEVEL"
EOF

    mkdir -p "$DUS_DIR/tasks"
    ok "配置文件已生成"
}

# ---------------------------------------------------------------------------
# 启动 / 停止 / 状态
# ---------------------------------------------------------------------------
start_bridge() {
    if is_running; then
        warn "Bridge 已在运行 (PID: $(cat $PID_FILE))"
        return
    fi

    if [ ! -f "$CONFIG_FILE" ]; then
        fail "配置文件不存在，请先运行 'dus setup' 或 ./dus-setup.sh"
    fi

    if [ -z "$BRIDGE_DIR" ]; then
        fail "未找到 bridge 代码。请运行安装脚本: curl -fsSL https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.sh | bash"
    fi

    info "启动 Bridge..."
    cd "$DUS_DIR"
    export PYTHONPATH="$PYTHONPATH_DIR:$PYTHONPATH"

    nohup python3 -m bridge.main > "$DUS_DIR/bridge-stdout.log" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 2

    if is_running; then
        ok "Bridge 已启动 (PID: $(cat $PID_FILE))"
        log_info "日志文件: $LOG_FILE"
    else
        fail "Bridge 启动失败，查看日志: cat $DUS_DIR/bridge-stdout.log"
    fi
}

stop_bridge() {
    if [ ! -f "$PID_FILE" ]; then
        warn "Bridge 未运行（无 PID 文件）"
        return
    fi

    local pid=$(cat "$PID_FILE")

    if ! kill -0 "$pid" 2>/dev/null; then
        log_info "Bridge 已停止（PID 文件过期）"
        rm -f "$PID_FILE"
        return
    fi

    info "停止 Bridge (PID: $pid)..."
    kill "$pid"

    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if kill -0 "$pid" 2>/dev/null; then
        log_warn "强制停止 Bridge..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    ok "Bridge 已停止"
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

show_status() {
    echo ""
    echo "${BOLD}=== DUS Bridge 状态 ===${RESET}"
    echo ""
    echo "  项目目录: $PROJECT_ROOT"
    echo "  配置目录: $DUS_DIR"
    echo "  配置文件: $CONFIG_FILE"

    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo -e "  运行状态: ${GREEN}运行中${RESET}"
        echo "  PID:      $pid"
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "  最近日志:"
            tail -5 "$LOG_FILE" | sed 's/^/    /'
        fi
    else
        echo -e "  运行状态: ${RED}未运行${RESET}"
    fi

    if [ -f "$CONFIG_FILE" ]; then
        echo ""
        echo "  配置文件内容:"
        cat "$CONFIG_FILE" | sed 's/^/    /'
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# 卸载
# ---------------------------------------------------------------------------
uninstall() {
    echo ""
    echo "${BOLD}=== 卸载 DUS Bridge ===${RESET}"
    echo ""

    if is_running; then
        stop_bridge
    fi

    read -p "确认删除 .dus 目录? (y/N): " confirm
    confirm=${confirm:-N}
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -rf "$DUS_DIR"
        ok ".dus 目录已删除"
    else
        log_info "卸载已取消"
    fi
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
main() {
    PROJECT_ID=$(generate_project_id)
    MACHINE_ID=$(generate_machine_id)

    # 优先从环境变量 DUS_MODE 读取模式（支持 curl | bash）
    local mode="${DUS_MODE:-}"
    local arg="${1:-}"

    # 如果 DUS_MODE 和参数冲突，参数优先
    if [ -n "$arg" ]; then
        case "$arg" in
            --auto|--start|--stop|--restart|--status|--uninstall|-h|--help)
                mode="$arg"
                ;;
            *)
                log_error "未知参数: $arg"
                show_help
                exit 1
                ;;
        esac
    fi

    case "$mode" in
        --auto|auto)
            auto_config
            generate_config
            start_bridge
            echo ""
            ok "安装完成"
            echo ""
            echo "  使用命令:"
            echo "    dus status    # 查看状态"
            echo "    dus restart   # 重启 Bridge"
            echo "    dus stop      # 停止 Bridge"
            echo ""
            ;;
        --start|start)
            start_bridge
            ;;
        --stop|stop)
            stop_bridge
            ;;
        --restart|restart)
            stop_bridge 2>/dev/null || true
            sleep 1
            start_bridge
            ;;
        --status|status)
            show_status
            ;;
        --uninstall|uninstall)
            uninstall
            ;;
        -h|--help|help)
            show_help
            ;;
        "")
            check_dependencies
            interactive_config
            generate_config
            start_bridge
            echo ""
            ok "安装完成"
            echo ""
            echo "  使用命令:"
            echo "    dus status    # 查看状态"
            echo "    dus restart   # 重启 Bridge"
            echo "    dus stop      # 停止 Bridge"
            echo "    dus setup     # 重新配置"
            echo ""
            echo "  日志查看:"
            echo "    tail -f $LOG_FILE"
            echo ""
            ;;
        *)
            log_error "未知模式: $mode"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
