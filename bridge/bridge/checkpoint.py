"""Checkpoint management for Session Resumption.

Stores task execution context in workdir/.dus_checkpoint.json so that if the
Bridge process crashes or is restarted mid-execution, the task can be resumed
from the checkpoint without waiting for the orphan-recovery timeout.

Checkpoint file format (JSON):
{
    "task_id": "...",
    "task_name": "...",
    "workdir": "...",
    "agent_type": "...",
    "agent_config": {...} | null,
    "created_at": "ISO timestamp"
}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

from loguru import logger


CHECKPOINT_FILENAME = ".dus_checkpoint.json"


@dataclass
class Checkpoint:
    task_id: str
    task_name: str
    workdir: str
    agent_type: str
    agent_config: dict | None
    created_at: str

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "workdir": self.workdir,
            "agent_type": self.agent_type,
            "agent_config": self.agent_config,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Checkpoint:
        return cls(
            task_id=data["task_id"],
            task_name=data["task_name"],
            workdir=data["workdir"],
            agent_type=data["agent_type"],
            agent_config=data.get("agent_config"),
            created_at=data["created_at"],
        )


def write_checkpoint(workdir: str, task_id: str, task_name: str, agent_type: str, agent_config: dict | None = None) -> str | None:
    """Write checkpoint file to workdir atomically. Returns the checkpoint path on success, None on failure."""
    checkpoint_path = os.path.join(workdir, CHECKPOINT_FILENAME)
    tmp_path = checkpoint_path + ".tmp"
    checkpoint = Checkpoint(
        task_id=task_id,
        task_name=task_name,
        workdir=workdir,
        agent_type=agent_type,
        agent_config=agent_config,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        # Write to temp file first for atomic replace
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Atomic rename (on POSIX, mostly atomic on Windows)
        os.replace(tmp_path, checkpoint_path)
        logger.debug(f"Checkpoint written: {checkpoint_path}")
        return checkpoint_path
    except Exception as e:
        logger.warning(f"Failed to write checkpoint {checkpoint_path}: {e}")
        # Clean up temp file if it exists
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return None


def read_checkpoint(workdir: str) -> Checkpoint | None:
    """Read checkpoint file from workdir. Returns None if not found or invalid."""
    checkpoint_path = os.path.join(workdir, CHECKPOINT_FILENAME)
    if not os.path.exists(checkpoint_path):
        return None
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Checkpoint.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to read checkpoint {checkpoint_path}: {e}")
        return None


def remove_checkpoint(workdir: str) -> bool:
    """Remove checkpoint file from workdir. Returns True if removed."""
    checkpoint_path = os.path.join(workdir, CHECKPOINT_FILENAME)
    if not os.path.exists(checkpoint_path):
        return False
    try:
        os.remove(checkpoint_path)
        logger.debug(f"Checkpoint removed: {checkpoint_path}")
        return True
    except Exception as e:
        logger.warning(f"Failed to remove checkpoint {checkpoint_path}: {e}")
        return False


def find_checkpoints(workdir_template: str) -> list[Checkpoint]:
    """Scan workdir_template directory for checkpoint files.
    Assumes workdirs are named after task identifiers.
    Returns list of valid checkpoints found.
    """
    checkpoints: list[Checkpoint] = []
    template_dir = Path(workdir_template).parent
    if not template_dir.exists():
        return checkpoints

    for entry in template_dir.iterdir():
        if entry.is_dir() and entry.name != ".dus":
            cp = read_checkpoint(str(entry))
            if cp:
                checkpoints.append(cp)
    return checkpoints
