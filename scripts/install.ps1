# DUS Bridge installer for Windows — one command to get started.
#
# Install CLI:
#   irm https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.ps1 | iex
#
# After installation, run `dus setup` in your project directory to configure.
#

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$RepoUrl       = "https://github.com/pwyyeye/dus.git"
$DefaultInstallDir = Join-Path $env:USERPROFILE ".dus"
$InstallDir    = if ($env:DUS_INSTALL_DIR) { $env:DUS_INSTALL_DIR } else { $DefaultInstallDir }
$BridgeDir     = Join-Path $InstallDir "bridge"
$VenvDir       = Join-Path $InstallDir "venv"
$BinDir        = Join-Path $InstallDir "bin"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Info  { param([string]$Msg) Write-Host "==> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "[OK] $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Warning $Msg }
function Write-Fail  { param([string]$Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red; exit 1 }

function Test-CommandExists {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Add-ToUserPath {
    param([string]$Dir)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -and $currentPath.Split(";") -contains $Dir) {
        return
    }
    $newPath = if ($currentPath) { "$currentPath;$Dir" } else { $Dir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    if ($env:Path -notlike "*$Dir*") {
        $env:Path = "$Dir;$env:Path"
    }
    Write-Info "Added $Dir to user PATH (restart your terminal for other sessions to pick it up)."
}

# ---------------------------------------------------------------------------
# System checks
# ---------------------------------------------------------------------------
function Test-Python {
    $python = $null
    if (Test-CommandExists "python") {
        $python = "python"
    } elseif (Test-CommandExists "python3") {
        $python = "python3"
    } else {
        Write-Fail "Python 3 is required but not installed.`n  Download from https://www.python.org/downloads/"
    }

    try {
        $verStr = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        $major, $minor = $verStr.Split(".")
        if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 10)) {
            Write-Fail "Python 3.10+ is required (found $verStr)."
        }
        Write-Ok "Python $verStr available"
        return $python
    } catch {
        Write-Fail "Could not determine Python version."
    }
}

# ---------------------------------------------------------------------------
# Bridge installation
# ---------------------------------------------------------------------------
function Install-Bridge {
    Write-Info "Installing DUS Bridge to $InstallDir..."

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    if (Test-Path (Join-Path $BridgeDir ".git")) {
        Write-Info "Updating existing bridge code..."
        Push-Location $BridgeDir
        git fetch origin main --depth 1 2>$null
        git reset --hard origin/main 2>$null
        Pop-Location
    } else {
        Write-Info "Cloning DUS repository..."
        if (-not (Test-CommandExists "git")) {
            Write-Fail "Git is not installed. Please install git and re-run."
        }
        if (Test-Path $BridgeDir) {
            Write-Warn "Removing incomplete installation..."
            Remove-Item $BridgeDir -Recurse -Force
        }
        git clone --depth 1 $RepoUrl $BridgeDir
    }

    Write-Ok "Bridge code ready at $BridgeDir"
}

function Install-Venv {
    param([string]$Python)
    if ((Test-Path $VenvDir) -and (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
        Write-Ok "Virtual environment already exists"
        return
    }

    Write-Info "Creating Python virtual environment..."
    & $Python -m venv $VenvDir
    Write-Ok "Virtual environment created"
}

function Install-Deps {
    $pip = Join-Path $VenvDir "Scripts\pip.exe"
    Write-Info "Installing Python dependencies..."
    & $pip install --upgrade pip 2>$null | Out-Null
    $req1 = Join-Path $BridgeDir "bridge\requirements.txt"
    $req2 = Join-Path $BridgeDir "requirements.txt"
    if (Test-Path $req1) {
        & $pip install -r $req1
    } else {
        & $pip install -r $req2
    }
    Write-Ok "Dependencies installed"
}

function Install-Cli {
    Write-Info "Installing dus CLI..."
    if (-not (Test-Path $BinDir)) {
        New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    }

    $dusCmd = Join-Path $BinDir "dus.cmd"
    @"
@echo off
setlocal enabledelayedexpansion

set DUS_HOME=%USERPROFILE%\.dus
set BRIDGE_DIR=%DUS_HOME%\bridge

if not exist "%BRIDGE_DIR%" (
  echo Error: Bridge not found at %BRIDGE_DIR%
  echo Please run the installer first:
  echo   irm https://raw.githubusercontent.com/pwyyeye/dus/main/scripts/install.ps1 ^| iex
  exit /b 1
)

set "CMD=%~1"
set "ARGS="

:argloop
shift
if "%~1"=="" goto endargs
if defined ARGS (
  set "ARGS=%ARGS% %1"
) else (
  set "ARGS=%1"
)
goto argloop

:endargs

if "%CMD%"=="setup" (
    powershell -ExecutionPolicy Bypass -File "%BRIDGE_DIR%\bridge\dus-setup.ps1" %ARGS%
) else if "%CMD%"=="start" (
    powershell -ExecutionPolicy Bypass -File "%BRIDGE_DIR%\bridge\dus-setup.ps1" --start
) else if "%CMD%"=="stop" (
    powershell -ExecutionPolicy Bypass -File "%BRIDGE_DIR%\bridge\dus-setup.ps1" --stop
) else if "%CMD%"=="restart" (
    powershell -ExecutionPolicy Bypass -File "%BRIDGE_DIR%\bridge\dus-setup.ps1" --restart
) else if "%CMD%"=="status" (
    powershell -ExecutionPolicy Bypass -File "%BRIDGE_DIR%\bridge\dus-setup.ps1" --status
) else if "%CMD%"=="--help" (
    echo DUS Bridge CLI
    echo.
    echo Usage: dus ^<command^>
    echo.
    echo Commands:
    echo   setup [--auto]   Configure bridge for the current project
    echo   start            Start the bridge daemon
    echo   stop             Stop the bridge daemon
    echo   restart          Restart the bridge daemon
    echo   status           Show bridge status
    echo.
    echo Run 'dus setup' in your project directory to get started.
) else (
    echo Error: unknown command '%CMD%'
    echo Run 'dus --help' for usage.
    exit /b 1
)
"@ | Set-Content -Path $dusCmd -Encoding ASCII

    Write-Ok "dus CLI installed to $dusCmd"

    Add-ToUserPath $BinDir
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  DUS Bridge - Installer" -ForegroundColor White
Write-Host ""

$python = Test-Python
Install-Bridge
Install-Venv -Python $python
Install-Deps
Install-Cli

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Green
Write-Host "  [OK] DUS Bridge CLI is ready!" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Next: configure your project"
Write-Host ""
Write-Host '     cd ~\your-project' -ForegroundColor Cyan
Write-Host '     dus setup' -ForegroundColor Cyan
Write-Host '     dus setup --auto' -ForegroundColor Cyan
Write-Host ""
Write-Host "  Manage:"
Write-Host "     dus start    # Start bridge"
Write-Host "     dus stop     # Stop bridge"
Write-Host "     dus status   # Show status"
Write-Host ""
