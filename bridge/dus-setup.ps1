# DUS Bridge project-level manager for Windows
#
# Usage:
#   .\dus-setup.ps1              # Interactive setup
#   .\dus-setup.ps1 --auto       # Auto mode
#   .\dus-setup.ps1 --start      # Start Bridge
#   .\dus-setup.ps1 --stop       # Stop Bridge
#   .\dus-setup.ps1 --restart    # Restart Bridge
#   .\dus-setup.ps1 --status     # Show status
#
# Environment variables:
#   $env:DUS_MODE="auto"         # Equivalent to --auto
#   $env:DUS_API_KEY="..."       # API key for auto mode
#   $env:DUS_API_URL="..."       # API URL for auto mode
#

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
function Write-Info  { param([string]$Msg) Write-Host "==> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "[OK] $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Warning $Msg }
function Write-Fail  { param([string]$Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }

# If running from global install dir (via dus CLI), use current working dir as project root
$GlobalInstallDir = Join-Path $env:USERPROFILE ".dus\bridge"
if ($ScriptDir -like "$GlobalInstallDir*") {
    $ProjectRoot = (Get-Location).Path
} else {
    $ProjectRoot = $ScriptDir
}

$DusDir       = Join-Path $ProjectRoot ".dus"
$ConfigFile   = Join-Path $DusDir "config.yaml"
$PidFile      = Join-Path $DusDir "bridge.pid"
$LogFile      = Join-Path $DusDir "bridge.log"

$DefaultApiUrl      = "http://localhost:8000/api/v1"
$DefaultPollInterval = 30
$DefaultTimeout     = 7200
$DefaultLogLevel    = "INFO"

$GlobalBridgeDir = Join-Path $env:USERPROFILE ".dus\bridge"

function Resolve-BridgeDir {
    $candidates = @(
        (Join-Path $ProjectRoot "bridge\bridge"),
        (Join-Path $GlobalBridgeDir "bridge"),
        (Join-Path $ProjectRoot "..\bridge\bridge")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            return (Split-Path $c -Parent)
        }
    }
    return $null
}

$BridgeDir = Resolve-BridgeDir
$PythonPathDir = if ($BridgeDir) { $BridgeDir } else { $ProjectRoot }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Get-ProjectId {
    $hash = [System.BitConverter]::ToString(
        [System.Security.Cryptography.MD5]::Create().ComputeHash(
            [System.Text.Encoding]::UTF8.GetBytes($ProjectRoot)
        )
    ).Replace("-", "").ToLower()
    return "proj-$($hash.Substring(0, 8))"
}

function Get-MachineId {
    $hash = [System.BitConverter]::ToString(
        [System.Security.Cryptography.MD5]::Create().ComputeHash(
            [System.Text.Encoding]::UTF8.GetBytes($ProjectRoot)
        )
    ).Replace("-", "").ToLower()
    $hostname = $env:COMPUTERNAME
    return "dev-$hostname-$($hash.Substring(0, 4))"
}

function Test-Running {
    if (Test-Path $PidFile) {
        $pidValue = [int](Get-Content $PidFile -Raw).Trim()
        try {
            $proc = Get-Process -Id $pidValue -ErrorAction Stop
            return $true
        } catch {
            return $false
        }
    }
    return $false
}

# ---------------------------------------------------------------------------
# Check deps
# ---------------------------------------------------------------------------
function Test-Dependencies {
    Write-Info "Checking dependencies..."

    $python = $null
    if (Get-Command python -ErrorAction SilentlyContinue) { $python = "python" }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $python = "python3" }
    else { Write-Fail "Python not found. Please install Python 3.10+" }

    $ver = & $python --version 2>&1
    Write-Ok "Python found: $ver"

    # Check packages
    $missing = @()
    try { & $python -c "import httpx" } catch { $missing += "httpx" }
    try { & $python -c "import loguru" } catch { $missing += "loguru" }
    try { & $python -c "import yaml" }   catch { $missing += "pyyaml" }

    if ($missing.Count -gt 0) {
        Write-Warn "Missing packages: $($missing -join ', ') — installing..."
        & $python -m pip install --user $missing
    }

    # Find claude
    $script:ClaudePath = ""
    if (Get-Command claude -ErrorAction SilentlyContinue) {
        $script:ClaudePath = (Get-Command claude).Source
    } elseif (Test-Path "$env:LOCALAPPDATA\Programs\Claude\claude.exe") {
        $script:ClaudePath = "$env:LOCALAPPDATA\Programs\Claude\claude.exe"
    }

    if (-not $script:ClaudePath) {
        Write-Warn "Claude CLI not found. Ensure Claude Code is installed."
        $script:ClaudePath = "claude"
    }

    Write-Ok "Dependencies OK"
}

# ---------------------------------------------------------------------------
# Interactive config
# ---------------------------------------------------------------------------
function Invoke-InteractiveConfig {
    Write-Host ""
    Write-Host "=== DUS Bridge Setup ===" -ForegroundColor White
    Write-Host ""
    Write-Host "  Project: $ProjectRoot"
    Write-Host "  Project ID: $ProjectId"
    Write-Host ""

    $apiUrl = Read-Host "Cloud API URL [$DefaultApiUrl]"
    if (-not $apiUrl) { $apiUrl = $DefaultApiUrl }

    $apiKey = Read-Host "API Key"
    while (-not $apiKey) {
        Write-Warn "API Key cannot be empty"
        $apiKey = Read-Host "API Key"
    }

    $defaultMachineName = "$env:COMPUTERNAME - $(Split-Path $ProjectRoot -Leaf)"
    $machineName = Read-Host "Machine name [$defaultMachineName]"
    if (-not $machineName) { $machineName = $defaultMachineName }

    $poll = Read-Host "Poll interval (seconds) [$DefaultPollInterval]"
    if (-not $poll) { $poll = $DefaultPollInterval }

    $timeout = Read-Host "Task timeout (seconds) [$DefaultTimeout]"
    if (-not $timeout) { $timeout = $DefaultTimeout }

    $claude = Read-Host "Claude path [$script:ClaudePath]"
    if (-not $claude) { $claude = $script:ClaudePath }

    Write-Host ""
    Write-Host "=== Summary ===" -ForegroundColor White
    Write-Host "  Project ID:   $ProjectId"
    Write-Host "  Machine ID:   $MachineId"
    Write-Host "  Machine Name: $machineName"
    Write-Host "  API URL:      $apiUrl"
    Write-Host "  Poll interval: ${poll}s"
    Write-Host "  Timeout:      ${timeout}s"
    Write-Host "  Claude path:   $claude"
    Write-Host ""

    $confirm = Read-Host "Confirm? (Y/n)"
    if ($confirm -and $confirm -notmatch "^[Yy]$") {
        Write-Info "Setup cancelled"
        exit 0
    }

    $script:ApiUrl = $apiUrl
    $script:ApiKey = $apiKey
    $script:MachineName = $machineName
    $script:PollInterval = $poll
    $script:Timeout = $timeout
    $script:ClaudePath = $claude
}

# ---------------------------------------------------------------------------
# Auto config
# ---------------------------------------------------------------------------
function Invoke-AutoConfig {
    Write-Info "Auto configuration mode..."

    $script:ApiUrl = if ($env:DUS_API_URL) { $env:DUS_API_URL } else { $DefaultApiUrl }
    if ($env:DUS_API_KEY) {
        $script:ApiKey = $env:DUS_API_KEY
    } else {
        $bytes = New-Object byte[] 16
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $script:ApiKey = ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLower()
        Write-Info "Auto-generated API Key: $($script:ApiKey)"
        Write-Info "Configure the same key in Cloud to verify."
    }

    $script:MachineName = "$env:COMPUTERNAME - $(Split-Path $ProjectRoot -Leaf)"
    $script:PollInterval = $DefaultPollInterval
    $script:Timeout = $DefaultTimeout

    if (-not $BridgeDir) {
        Write-Warn "Bridge code not found, downloading from GitHub..."
        $zip = Join-Path $ProjectRoot "dus-main.zip"
        Invoke-WebRequest -Uri "https://github.com/pwyyeye/dus/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath $ProjectRoot -Force
        if (Test-Path (Join-Path $ProjectRoot "dus-main\bridge")) {
            Copy-Item -Recurse (Join-Path $ProjectRoot "dus-main\bridge") (Join-Path $ProjectRoot "bridge")
        }
        Remove-Item $zip -Force
        Remove-Item (Join-Path $ProjectRoot "dus-main") -Recurse -Force
        $script:BridgeDir = Resolve-BridgeDir
        $script:PythonPathDir = if ($BridgeDir) { $BridgeDir } else { $ProjectRoot }
    }

    Write-Ok "Configuration done"
}

# ---------------------------------------------------------------------------
# Generate config
# ---------------------------------------------------------------------------
function New-Config {
    Write-Info "Generating config: $ConfigFile"
    New-Item -ItemType Directory -Path $DusDir -Force | Out-Null

    $yaml = @"
version: "1.0.0"

machine:
  machine_id: "$MachineId"
  machine_name: "$MachineName"
  agent_type: "claude_code"
  agent_capability: "remote_execution"
  project_id: "$ProjectId"

cloud:
  api_url: "$ApiUrl"
  api_key: "$ApiKey"
  poll_interval: $PollInterval

agent:
  path: "$ClaudePath"
  workdir_template: "$($DusDir -replace '\\', '/')/tasks/{task_id}"
  timeout: $Timeout

logging:
  level: "$DefaultLogLevel"
"@

    $yaml | Set-Content -Path $ConfigFile -Encoding UTF8
    New-Item -ItemType Directory -Path (Join-Path $DusDir "tasks") -Force | Out-Null
    Write-Ok "Config generated"
}

# ---------------------------------------------------------------------------
# Start / Stop / Status
# ---------------------------------------------------------------------------
function Start-Bridge {
    if (Test-Running) {
        Write-Warn "Bridge already running (PID: $(Get-Content $PidFile))"
        return
    }

    if (-not (Test-Path $ConfigFile)) {
        Write-Fail "Config not found. Run 'dus setup' first."
    }

    if (-not $BridgeDir) {
        Write-Fail "Bridge code not found. Run installer first:`n  irm https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.ps1 | iex"
    }

    Write-Info "Starting Bridge..."
    $env:PYTHONPATH = "$PythonPathDir;$env:PYTHONPATH"

    $python = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "python3" }
    $logPath = Join-Path $DusDir "bridge-stdout.log"

    $proc = Start-Process -FilePath $python -ArgumentList "-m","bridge.main" `
        -WorkingDirectory $DusDir -WindowStyle Hidden `
        -RedirectStandardOutput $logPath -RedirectStandardError $logPath -PassThru

    $proc.Id | Set-Content -Path $PidFile
    Start-Sleep -Seconds 2

    if (Test-Running) {
        Write-Ok "Bridge started (PID: $($proc.Id))"
        Write-Info "Log: $LogFile"
    } else {
        Write-Fail "Bridge failed to start. Check: $logPath"
    }
}

function Stop-Bridge {
    if (-not (Test-Path $PidFile)) {
        Write-Warn "Bridge not running"
        return
    }

    $pidValue = [int](Get-Content $PidFile -Raw).Trim()
    try { $null = Get-Process -Id $pidValue -ErrorAction Stop } catch {
        Write-Info "Bridge already stopped (stale PID file)"
        Remove-Item $PidFile -Force
        return
    }

    Write-Info "Stopping Bridge (PID: $pidValue)..."
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue

    $count = 0
    while ($count -lt 10) {
        try { $null = Get-Process -Id $pidValue -ErrorAction Stop; Start-Sleep 1; $count++ } catch { break }
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Ok "Bridge stopped"
}

function Show-Status {
    Write-Host ""
    Write-Host "=== DUS Bridge Status ===" -ForegroundColor White
    Write-Host ""
    Write-Host "  Project:   $ProjectRoot"
    Write-Host "  Config:    $ConfigFile"

    if (Test-Running) {
        $pidValue = [int](Get-Content $PidFile -Raw).Trim()
        Write-Host "  Status:    " -NoNewline; Write-Host "Running" -ForegroundColor Green
        Write-Host "  PID:       $pidValue"
        if (Test-Path $LogFile) {
            Write-Host ""
            Write-Host "  Recent logs:"
            Get-Content $LogFile -Tail 5 | ForEach-Object { Write-Host "    $_" }
        }
    } else {
        Write-Host "  Status:    " -NoNewline; Write-Host "Stopped" -ForegroundColor Red
    }

    if (Test-Path $ConfigFile) {
        Write-Host ""
        Write-Host "  Config:"
        Get-Content $ConfigFile | ForEach-Object { Write-Host "    $_" }
    }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
$ProjectId = Get-ProjectId
$MachineId = Get-MachineId

$mode = if ($env:DUS_MODE) { $env:DUS_MODE.ToLower() } else { "" }
if ($args.Count -gt 0) { $mode = $args[0].ToLower().TrimStart("-") }

switch ($mode) {
    "auto" {
        Invoke-AutoConfig
        New-Config
        Start-Bridge
        Write-Host ""
        Write-Ok "Setup complete"
        Write-Host "  dus status   # Show status"
        Write-Host "  dus restart  # Restart"
        Write-Host "  dus stop     # Stop"
    }
    "start"  { Start-Bridge }
    "stop"   { Stop-Bridge }
    "restart" { Stop-Bridge; Start-Sleep 1; Start-Bridge }
    "status" { Show-Status }
    "uninstall" {
        if (Test-Running) { Stop-Bridge }
        $confirm = Read-Host "Delete .dus directory? (y/N)"
        if ($confirm -match "^[Yy]$") {
            Remove-Item $DusDir -Recurse -Force
            Write-Ok ".dus removed"
        } else {
            Write-Info "Uninstall cancelled"
        }
    }
    "help"   { Write-Host "Usage: dus-setup.ps1 [--auto|--start|--stop|--restart|--status|--uninstall]" }
    default  {
        Test-Dependencies
        Invoke-InteractiveConfig
        New-Config
        Start-Bridge
        Write-Host ""
        Write-Ok "Setup complete"
        Write-Host "  dus status   # Show status"
        Write-Host "  dus restart  # Restart"
        Write-Host "  dus stop     # Stop"
        Write-Host "  dus setup    # Reconfigure"
        Write-Host ""
        Write-Host "  Logs: tail -f $LogFile"
    }
}
