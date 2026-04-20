#!/bin/bash
# =============================================================================
# DUS Bridge 一键安装脚本
#
# 在项目目录下运行此脚本，自动完成 Bridge 安装和启动。
# 支持多项目多实例：同一设备的不同项目目录可各自运行独立的 Bridge。
#
# 使用方式:
#   ./dus-setup.sh                  # 交互式安装
#   ./dus-setup.sh --auto           # 自动使用默认配置
#   ./dus-setup.sh --stop           # 停止 Bridge
#   ./dus-setup.sh --restart        # 重启 Bridge
#   ./dus-setup.sh --status         # 查看状态
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR" && pwd)"
DUS_DIR="$PROJECT_ROOT/.dus"

# Bridge 配置文件
CONFIG_FILE="$DUS_DIR/config.yaml"
PID_FILE="$DUS_DIR/bridge.pid"
LOG_FILE="$DUS_DIR/bridge.log"

# 默认值
DEFAULT_API_URL="http://localhost:8000/api/v1"
DEFAULT_POLL_INTERVAL=30
DEFAULT_TIMEOUT=7200
DEFAULT_LOG_LEVEL="INFO"

# =============================================================================
# 帮助信息
# =============================================================================

show_help() {
    cat << EOF
DUS Bridge 一键安装脚本

用法: ./dus-setup.sh [选项]

选项:
    --auto       自动使用默认配置（不提示输入）
    --stop       停止 Bridge
    --restart    重启 Bridge
    --status     查看 Bridge 状态
    --uninstall  卸载 Bridge（删除 .dus 目录）
    -h, --help   显示帮助信息

示例:
    ./dus-setup.sh              # 交互式安装
    ./dus-setup.sh --auto       # 自动安装（使用默认配置）
    ./dus-setup.sh --stop       # 停止 Bridge
EOF
}

# =============================================================================
# 颜色输出函数
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# 检查依赖
# =============================================================================

check_dependencies() {
    log_info "检查依赖..."

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装，请先安装 Python 3.10+"
        exit 1
    fi

    # 检查 pip
    if ! python3 -m pip --version &> /dev/null; then
        log_error "pip 未安装，请先安装 pip"
        exit 1
    fi

    # 检查 httpx
    if ! python3 -c "import httpx" 2>/dev/null; then
        log_warn "httpx 未安装，正在安装..."
        python3 -m pip install --user --break-system-packages httpx loguru pyyaml
    fi

    # 检查 Claude
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

    log_info "依赖检查完成"
}

# =============================================================================
# 生成项目 ID
# =============================================================================

generate_project_id() {
    # 基于项目路径生成稳定的 project_id
    echo "proj-$(echo -n "$PROJECT_ROOT" | md5sum | cut -c1-8)"
}

# =============================================================================
# 生成设备 ID
# =============================================================================

generate_machine_id() {
    local project_suffix=$(echo -n "$PROJECT_ROOT" | md5sum | cut -c1-4)
    echo "dev-$(hostname)-${project_suffix}"
}

# =============================================================================
# 交互式配置
# =============================================================================

interactive_config() {
    echo ""
    echo "=== DUS Bridge 安装配置 ==="
    echo ""
    echo "项目目录: $PROJECT_ROOT"
    echo "项目 ID:  $PROJECT_ID"
    echo ""

    # 云端 API URL
    read -p "云端 API URL [$DEFAULT_API_URL]: " API_URL
    API_URL=${API_URL:-$DEFAULT_API_URL}

    # API Key
    read -p "API Key: " API_KEY
    while [ -z "$API_KEY" ]; do
        log_error "API Key 不能为空"
        read -p "API Key: " API_KEY
    done

    # 设备名称
    DEFAULT_MACHINE_NAME="$(hostname) - $(basename "$PROJECT_ROOT")"
    read -p "设备名称 [$DEFAULT_MACHINE_NAME]: " MACHINE_NAME
    MACHINE_NAME=${MACHINE_NAME:-$DEFAULT_MACHINE_NAME}

    # 轮询间隔
    read -p "轮询间隔(秒) [$DEFAULT_POLL_INTERVAL]: " POLL_INTERVAL
    POLL_INTERVAL=${POLL_INTERVAL:-$DEFAULT_POLL_INTERVAL}

    # 执行超时
    read -p "任务超时时间(秒) [$DEFAULT_TIMEOUT]: " TIMEOUT
    TIMEOUT=${TIMEOUT:-$DEFAULT_TIMEOUT}

    # Claude 路径
    read -p "Claude 路径 [$CLAUDE_PATH]: " CLAUDE_PATH_INPUT
    CLAUDE_PATH=${CLAUDE_PATH_INPUT:-$CLAUDE_PATH}

    echo ""
    echo "=== 配置摘要 ==="
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

# =============================================================================
# 自动配置（使用默认值）
# =============================================================================

auto_config() {
    log_info "使用自动配置模式..."

    API_URL="$DEFAULT_API_URL"
    API_KEY="${DUS_API_KEY:-}"
    MACHINE_NAME="$(hostname) - $(basename "$PROJECT_ROOT")"
    POLL_INTERVAL="$DEFAULT_POLL_INTERVAL"
    TIMEOUT="$DEFAULT_TIMEOUT"

    if [ -z "$API_KEY" ]; then
        log_error "自动模式需要设置 DUS_API_KEY 环境变量"
        exit 1
    fi

    # 下载 bridge 代码（如果项目目录下没有）
    if [ ! -d "$PROJECT_ROOT/bridge/bridge" ]; then
        log_info "下载 Bridge 代码..."
        cd "$PROJECT_ROOT"
        curl -sL "https://github.com/pwyyeye/dus/archive/refs/heads/main.zip" -o dus-main.zip
        unzip -q -o dus-main.zip
        # 解压后的目录名是 dus-main，包含 bridge/ cloud/ 等
        if [ -d "dus-main/bridge" ]; then
            # 只提取 bridge 目录
            cp -r dus-main/bridge "$PROJECT_ROOT/bridge"
            cp dus-main/bridge/dus-setup.sh "$PROJECT_ROOT/dus-setup.sh" 2>/dev/null || true
        fi
        rm -rf dus-main dus-main.zip
        log_info "Bridge 代码已下载到 $PROJECT_ROOT/bridge"
    fi

    log_info "配置完成"
}

# =============================================================================
# 生成配置文件
# =============================================================================

generate_config() {
    log_info "生成配置文件: $CONFIG_FILE"

    mkdir -p "$DUS_DIR"

    cat > "$CONFIG_FILE" << EOF
version: "1.0.0"

machine:
  machine_id: "$MACHINE_ID"
  machine_name: "$MACHINE_NAME"
  agent_type: "claude_code"
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

    # 创建任务工作目录
    mkdir -p "$DUS_DIR/tasks"

    log_info "配置文件已生成"
}

# =============================================================================
# 安装依赖
# =============================================================================

install_dependencies() {
    log_info "安装 Python 依赖..."

    python3 -m pip install --user --break-system-packages httpx loguru pyyaml

    log_info "依赖安装完成"
}

# =============================================================================
# 启动 Bridge
# =============================================================================

start_bridge() {
    # 检查是否已运行
    if is_running; then
        log_warn "Bridge 已在运行 (PID: $(cat $PID_FILE))"
        return
    fi

    # 检查配置文件
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "配置文件不存在，请先运行安装"
        exit 1
    fi

    log_info "启动 Bridge..."

    cd "$DUS_DIR"

    # 设置 PYTHONPATH，指向 bridge 模块所在目录
    # bridge 代码位于 $PROJECT_ROOT/bridge/bridge/main.py
    export PYTHONPATH="$PROJECT_ROOT/bridge:$PYTHONPATH"

    # 启动 Bridge（后台运行）
    nohup python3 -m bridge.main > "$DUS_DIR/bridge-stdout.log" 2>&1 &
    echo $! > "$PID_FILE"

    # 等待启动
    sleep 2

    # 检查是否启动成功
    if is_running; then
        log_info "Bridge 已启动 (PID: $(cat $PID_FILE))"
        log_info "日志文件: $LOG_FILE"
    else
        log_error "Bridge 启动失败"
        log_info "查看日志: cat $DUS_DIR/bridge-stdout.log"
        exit 1
    fi
}

# =============================================================================
# 停止 Bridge
# =============================================================================

stop_bridge() {
    if [ ! -f "$PID_FILE" ]; then
        log_warn "Bridge 未运行（无 PID 文件）"
        return
    fi

    local pid=$(cat "$PID_FILE")

    if ! kill -0 "$pid" 2>/dev/null; then
        log_info "Bridge 已停止（PID 文件过期）"
        rm -f "$PID_FILE"
        return
    fi

    log_info "停止 Bridge (PID: $pid)..."
    kill "$pid"

    # 等待进程结束
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    # 如果还在运行，强制杀掉
    if kill -0 "$pid" 2>/dev/null; then
        log_warn "强制停止 Bridge..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    log_info "Bridge 已停止"
}

# =============================================================================
# 检查 Bridge 是否运行
# =============================================================================

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# =============================================================================
# 查看状态
# =============================================================================

show_status() {
    echo ""
    echo "=== DUS Bridge 状态 ==="
    echo ""
    echo "项目目录: $PROJECT_ROOT"
    echo "配置目录: $DUS_DIR"
    echo "配置文件: $CONFIG_FILE"

    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo -e "运行状态: ${GREEN}运行中${NC}"
        echo "PID:     $pid"

        # 显示最后几行日志
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "=== 最近日志 ==="
            tail -5 "$LOG_FILE"
        fi
    else
        echo -e "运行状态: ${RED}未运行${NC}"
    fi

    if [ -f "$CONFIG_FILE" ]; then
        echo ""
        echo "=== 配置文件内容 ==="
        cat "$CONFIG_FILE"
    fi

    echo ""
}

# =============================================================================
# 卸载
# =============================================================================

uninstall() {
    echo ""
    echo "=== 卸载 DUS Bridge ==="
    echo ""

    # 停止 Bridge
    if is_running; then
        stop_bridge
    fi

    read -p "确认删除 .dus 目录? (y/N): " confirm
    confirm=${confirm:-N}
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        log_info "删除 $DUS_DIR"
        rm -rf "$DUS_DIR"
        log_info "卸载完成"
    else
        log_info "卸载已取消"
    fi
}

# =============================================================================
# 主流程
# =============================================================================

main() {
    # 生成 ID
    PROJECT_ID=$(generate_project_id)
    MACHINE_ID=$(generate_machine_id)

    # 解析参数
    case "${1:-}" in
        --auto)
            auto_config
            generate_config
            install_dependencies
            start_bridge
            ;;
        --stop)
            stop_bridge
            ;;
        --restart)
            stop_bridge 2>/dev/null || true
            start_bridge
            ;;
        --status)
            show_status
            ;;
        --uninstall)
            uninstall
            ;;
        -h|--help)
            show_help
            ;;
        "")
            check_dependencies
            interactive_config
            generate_config
            install_dependencies
            start_bridge

            echo ""
            echo "=== 安装完成 ==="
            echo ""
            echo "使用命令:"
            echo "  ./dus-setup.sh --status   # 查看状态"
            echo "  ./dus-setup.sh --restart  # 重启 Bridge"
            echo "  ./dus-setup.sh --stop     # 停止 Bridge"
            echo "  ./dus-setup.sh --uninstall  # 卸载"
            echo ""
            echo "日志查看:"
            echo "  tail -f $LOG_FILE"
            echo ""
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
