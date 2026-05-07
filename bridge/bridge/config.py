from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class MachineConfig:
    machine_id: str = "CHANGE_ME"
    machine_name: str = "CHANGE_ME"
    agent_type: str = "claude_code"
    agent_capability: str = "remote_execution"
    project_id: str | None = None


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
class BridgeConfig:
    machine: MachineConfig = field(default_factory=MachineConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


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
    )

    # Environment variable overrides
    if os.getenv("DUS_API_KEY"):
        cfg.cloud.api_key = os.getenv("DUS_API_KEY")
    if os.getenv("DUS_API_URL"):
        cfg.cloud.api_url = os.getenv("DUS_API_URL")
    if os.getenv("DUS_MACHINE_ID"):
        cfg.machine.machine_id = os.getenv("DUS_MACHINE_ID")

    # Validate required fields
    for field_name, value in [
        ("machine.machine_id", cfg.machine.machine_id),
        ("cloud.api_key", cfg.cloud.api_key),
        ("cloud.api_url", cfg.cloud.api_url),
    ]:
        if value == "CHANGE_ME":
            print(f"ERROR: Please set '{field_name}' in config.yaml (currently 'CHANGE_ME')")
            sys.exit(1)

    return cfg
