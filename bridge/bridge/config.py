from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Agent CLI default binary names on PATH
_DEFAULT_AGENT_BINS: dict[str, str] = {
    "claude_code": "claude",
    "codex": "codex",
    "hermes_agent": "hermes",
    "openclaw": "openclaw",
    "kimi": "kimi-cli",
}

# Environment variable overrides for agent path
_AGENT_PATH_ENV_VARS: dict[str, str] = {
    "claude_code": "DUS_CLAUDE_PATH",
    "codex": "DUS_CODEX_PATH",
    "hermes_agent": "DUS_HERMES_PATH",
    "openclaw": "DUS_OPENCLAW_PATH",
    "kimi": "DUS_KIMI_PATH",
}


def detect_agent_path(agent_type: str, configured_path: str | None = None) -> str:
    """Detect agent CLI executable path.

    Resolution order (highest priority first):
    1. Environment variable (e.g. DUS_CLAUDE_PATH)
    2. Configured path from config.yaml (if not default/empty)
    3. shutil.which() on PATH using default binary name

    Raises SystemExit if no executable is found.
    """
    # 1. Env var override
    env_var = _AGENT_PATH_ENV_VARS.get(agent_type)
    if env_var and os.getenv(env_var):
        env_path = os.getenv(env_var)
        if shutil.which(env_path):
            return env_path
        print(f"WARNING: {env_var}={env_path} not found on PATH, falling back...")

    # 2. Configured path (if explicitly set and differs from default)
    if configured_path and configured_path != _DEFAULT_AGENT_BINS.get(agent_type, configured_path):
        if shutil.which(configured_path):
            return configured_path
        print(f"WARNING: Configured agent path '{configured_path}' not found, trying PATH...")

    # 3. Auto-detect from PATH
    bin_name = _DEFAULT_AGENT_BINS.get(agent_type, agent_type)
    detected = shutil.which(bin_name)
    if detected:
        return detected

    print(f"ERROR: No agent CLI found for '{agent_type}'.")
    print(f"  Tried: {env_var or '(no env var)'}, config path, '{bin_name}' on PATH")
    print(f"  Install the agent CLI or set {env_var} to the full path.")
    sys.exit(1)


@dataclass
class MachineConfig:
    machine_id: str = "CHANGE_ME"
    machine_name: str = "CHANGE_ME"
    agent_capability: str = "remote_execution"
    project_id: str | None = None
    project_root: str | None = None


@dataclass
class CloudConfig:
    api_url: str = "http://localhost:8000/api/v1"
    api_key: str = "CHANGE_ME"
    poll_interval: int = 60


@dataclass
class AgentConfig:
    path: str = "claude"
    workdir_template: str = "/tmp/dus_task_{task_id}"
    timeout: int = 3600


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class HealthConfig:
    port: int = 19514


@dataclass
class GCConfig:
    enabled: bool = True
    interval: int = 3600
    ttl: int = 86400


@dataclass
class BridgeConfig:
    machine: MachineConfig = field(default_factory=MachineConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    gc: GCConfig = field(default_factory=GCConfig)
    max_concurrent_tasks: int = 3


def detect_available_agents() -> list[dict]:
    """Detect which agent CLIs are available on this machine.

    Resolution order per agent type (highest priority first):
    1. Environment variable (e.g. DUS_CLAUDE_PATH)
    2. shutil.which() on PATH using default binary name

    Returns a list of dicts: [{"agent_type": ..., "path": ..., "version": ...}]
    """
    agents = []
    for agent_type, bin_name in _DEFAULT_AGENT_BINS.items():
        resolved = None
        # 1. Env var override
        env_var = _AGENT_PATH_ENV_VARS.get(agent_type)
        if env_var and os.getenv(env_var):
            env_path = os.getenv(env_var)
            if shutil.which(env_path):
                resolved = env_path
        # 2. Auto-detect from PATH
        if not resolved:
            resolved = shutil.which(bin_name)
        if not resolved:
            continue
        version = "unknown"
        try:
            result = subprocess.run(
                [resolved, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            text = (result.stdout.strip() or result.stderr.strip())
            version = text.splitlines()[0] if text else "unknown"
        except Exception:
            pass
        agents.append({
            "agent_type": agent_type,
            "path": resolved,
            "version": version,
        })
    return agents


def load_config(config_path: str = "config.yaml") -> BridgeConfig:
    """Load config from YAML file with env var overrides."""
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        print("Copy config.yaml.example to config.yaml and edit it.")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = BridgeConfig(
        machine=MachineConfig(**(raw.get("machine", {}))),
        cloud=CloudConfig(**(raw.get("cloud", {}))),
        agent=AgentConfig(**(raw.get("agent", {}))),
        logging=LoggingConfig(**(raw.get("logging", {}))),
        health=HealthConfig(**(raw.get("health", {}))),
        gc=GCConfig(**(raw.get("gc", {}))),
    )

    # Top-level overrides
    if "max_concurrent_tasks" in raw:
        cfg.max_concurrent_tasks = raw["max_concurrent_tasks"]

    # Environment variable overrides
    if os.getenv("DUS_API_KEY"):
        cfg.cloud.api_key = os.getenv("DUS_API_KEY")
    if os.getenv("DUS_API_URL"):
        cfg.cloud.api_url = os.getenv("DUS_API_URL")
    if os.getenv("DUS_MACHINE_ID"):
        cfg.machine.machine_id = os.getenv("DUS_MACHINE_ID")
    if os.getenv("DUS_HEALTH_PORT"):
        cfg.health.port = int(os.getenv("DUS_HEALTH_PORT"))

    # Validate required fields
    for field_name, value in [
        ("machine.machine_id", cfg.machine.machine_id),
        ("cloud.api_key", cfg.cloud.api_key),
        ("cloud.api_url", cfg.cloud.api_url),
    ]:
        if value == "CHANGE_ME":
            print(f"ERROR: Please set '{field_name}' in config.yaml (currently 'CHANGE_ME')")
            sys.exit(1)

    # Agent paths are resolved per-agent-type at bridge startup (not here, since
    # there is no single agent_type — the bridge registers one machine per agent CLI).

    # Auto-set project_root from current working directory if not configured
    if not cfg.machine.project_root:
        cwd = os.getcwd()
        if os.path.basename(cwd) == ".dus":
            cwd = os.path.dirname(cwd)
        cfg.machine.project_root = cwd

    return cfg
