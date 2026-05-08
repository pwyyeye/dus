#!/usr/bin/env bash
# DUS Bridge installer — one command to install the DUS CLI.
#
# Install / upgrade CLI only:
#   curl -fsSL https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.sh | bash
#
# After installation, run `dus setup` in your project directory to configure.
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_URL="https://github.com/pwyyeye/dus.git"
REPO_WEB_URL="https://github.com/pwyyeye/dus"
INSTALL_DIR="${DUS_INSTALL_DIR:-$HOME/.dus}"
BRIDGE_DIR="$INSTALL_DIR/bridge"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$INSTALL_DIR/bin"

# Colors (disabled when not a terminal)
if [ -t 1 ] || [ -t 2 ]; then
  BOLD='\033[1m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  RED='\033[0;31m'
  CYAN='\033[0;36m'
  DARKGRAY='\033[1;30m'
  RESET='\033[0m'
else
  BOLD='' GREEN='' YELLOW='' RED='' CYAN='' DARKGRAY='' RESET=''
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { printf "${BOLD}${CYAN}==> %s${RESET}\n" "$*"; }
ok()    { printf "${BOLD}${GREEN}✓ %s${RESET}\n" "$*"; }
warn()  { printf "${BOLD}${YELLOW}⚠ %s${RESET}\n" "$*" >&2; }
fail()  { printf "${BOLD}${RED}✗ %s${RESET}\n" "$*" >&2; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

add_to_path() {
  local dir="$1"
  local line="export PATH=\"$dir:\$PATH\""
  for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ] && ! grep -qF "$dir" "$rc"; then
      printf '\n# Added by DUS installer\n%s\n' "$line" >> "$rc"
    fi
  done
}

# ---------------------------------------------------------------------------
# System checks
# ---------------------------------------------------------------------------
check_python() {
  if command_exists python3; then
    PYTHON=python3
  elif command_exists python; then
    PYTHON=python
  else
    fail "Python 3 is required but not installed.\n  macOS: brew install python3\n  Linux: sudo apt install python3 python3-venv"
  fi

  local py_ver
  py_ver=$($PYTHON -c 'import sys; print(sys.version_info.major, sys.version_info.minor)' 2>/dev/null || echo "0 0")
  local major=$(echo "$py_ver" | awk '{print $1}')
  local minor=$(echo "$py_ver" | awk '{print $2}')
  if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 10 ]; }; then
    fail "Python 3.10+ is required (found ${major}.${minor})."
  fi

  ok "Python $major.$minor available"
}

# ---------------------------------------------------------------------------
# Bridge installation
# ---------------------------------------------------------------------------
install_bridge() {
  info "Installing DUS Bridge to $INSTALL_DIR..."

  mkdir -p "$INSTALL_DIR"

  if [ -d "$BRIDGE_DIR/.git" ]; then
    info "Updating existing bridge code..."
    cd "$BRIDGE_DIR"
    git fetch origin main --depth 1 2>/dev/null || true
    git reset --hard origin/main 2>/dev/null || true
  else
    info "Cloning DUS repository..."
    if ! command_exists git; then
      fail "Git is not installed. Please install git and re-run."
    fi
    if [ -d "$BRIDGE_DIR" ]; then
      warn "Removing incomplete installation..."
      rm -rf "$BRIDGE_DIR"
    fi
    git clone --depth 1 "$REPO_URL" "$BRIDGE_DIR"
  fi

  ok "Bridge code ready at $BRIDGE_DIR"
}

install_venv() {
  if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ]; then
    ok "Virtual environment already exists"
    return
  fi

  info "Creating Python virtual environment..."
  $PYTHON -m venv "$VENV_DIR"
  ok "Virtual environment created"
}

install_deps() {
  info "Installing Python dependencies..."
  "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
  # Try root-level requirements first (repo clone puts it at $BRIDGE_DIR/requirements.txt)
  "$VENV_DIR/bin/pip" install -r "$BRIDGE_DIR/requirements.txt" 2>/dev/null || \
    "$VENV_DIR/bin/pip" install -r "$BRIDGE_DIR/bridge/requirements.txt"
  ok "Dependencies installed"
}

install_cli() {
  info "Installing dus CLI..."
  mkdir -p "$BIN_DIR"

  cat > "$BIN_DIR/dus" << 'EOF'
#!/usr/bin/env bash
# DUS Bridge CLI wrapper

DUS_HOME="${DUS_INSTALL_DIR:-$HOME/.dus}"
BRIDGE_DIR="$DUS_HOME/bridge"
VENV_DIR="$DUS_HOME/venv"

if [ ! -d "$BRIDGE_DIR" ]; then
  echo "Error: Bridge not found at $BRIDGE_DIR"
  echo "Please run the installer first:"
  echo '  curl -fsSL https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.sh | bash'
  exit 1
fi

case "${1:-}" in
  setup)
    shift
    bash "$BRIDGE_DIR/bridge/dus-setup.sh" "$@"
    ;;
  start)
    bash "$BRIDGE_DIR/bridge/dus-setup.sh" --start
    ;;
  stop)
    bash "$BRIDGE_DIR/bridge/dus-setup.sh" --stop
    ;;
  restart)
    bash "$BRIDGE_DIR/bridge/dus-setup.sh" --restart
    ;;
  status)
    bash "$BRIDGE_DIR/bridge/dus-setup.sh" --status
    ;;
  --help|-h|help)
    echo "DUS Bridge CLI"
    echo ""
    echo "Usage: dus <command>"
    echo ""
    echo "Commands:"
    echo "  setup [--auto]   Configure bridge for the current project"
    echo "  start            Start the bridge daemon"
    echo "  stop             Stop the bridge daemon"
    echo "  restart          Restart the bridge daemon"
    echo "  status           Show bridge status"
    echo ""
    echo "Run 'dus setup' in your project directory to get started."
    ;;
  *)
    echo "Error: unknown command '${1:-}'"
    echo "Run 'dus --help' for usage."
    exit 1
    ;;
esac
EOF

  chmod +x "$BIN_DIR/dus"
  ok "dus CLI installed to $BIN_DIR/dus"

  # Add to PATH if needed
  if ! echo "$PATH" | tr ':' '\n' | grep -q "^$BIN_DIR$"; then
    export PATH="$BIN_DIR:$PATH"
    add_to_path "$BIN_DIR"
    info "Added $BIN_DIR to PATH (restart your shell to pick it up in new sessions)"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  printf "\n"
  printf "${BOLD}  DUS Bridge — Installer${RESET}\n"
  printf "\n"

  check_python
  install_bridge
  install_venv
  install_deps
  install_cli

  printf "\n"
  printf "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  printf "${BOLD}${GREEN}  ✓ DUS Bridge CLI is ready!${RESET}\n"
  printf "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  printf "\n"
  printf "  ${BOLD}Next: configure your project${RESET}\n"
  printf "\n"
  printf "     ${CYAN}cd ~/your-project${RESET}\n"
  printf "     ${CYAN}dus setup${RESET}         ${DARKGRAY}# Interactive setup${RESET}\n"
  printf "     ${CYAN}dus setup --auto${RESET}  ${DARKGRAY}# Auto mode${RESET}\n"
  printf "\n"
  printf "  ${BOLD}Manage:${RESET}\n"
  printf "     ${CYAN}dus start${RESET}    # Start bridge\n"
  printf "     ${CYAN}dus stop${RESET}     # Stop bridge\n"
  printf "     ${CYAN}dus status${RESET}   # Show status\n"
  printf "\n"
}

main "$@"
