from __future__ import annotations

import os
import uuid
from pathlib import Path

from loguru import logger


# Machine UUID persistence inspired by Multica's daemon.id:
# - Stable across restarts, hostname changes, and config edits
# - Stored atomically with restricted permissions
# - Falls back to fresh UUID on corruption

_MACHINE_UUID_FILE = Path.home() / ".dus" / "machine.uuid"


def ensure_machine_uuid(configured_id: str | None = None) -> str:
    """Return a stable machine UUID.

    Resolution order:
    1. Environment variable DUS_MACHINE_UUID
    2. Existing ~/.dus/machine.uuid file
    3. Configured machine_id (if it looks like a UUID)
    4. Generate a new UUID v4 and persist it
    """
    # 1. Env var override
    env_uuid = os.getenv("DUS_MACHINE_UUID", "").strip()
    if env_uuid:
        return env_uuid

    # 2. Existing persistent file
    if _MACHINE_UUID_FILE.exists():
        try:
            data = _MACHINE_UUID_FILE.read_text(encoding="utf-8").strip()
            if data:
                # Validate it's a valid UUID
                uuid.UUID(data)
                return data
        except Exception:
            logger.warning("Machine UUID file is corrupt, regenerating...")

    # 3. Configured machine_id if it is already a UUID
    if configured_id and configured_id != "CHANGE_ME":
        try:
            uuid.UUID(configured_id)
            _write_uuid_file(configured_id)
            return configured_id
        except ValueError:
            pass

    # 4. Generate and persist new UUID
    new_uuid = uuid.uuid4().hex
    _write_uuid_file(new_uuid)
    logger.info(f"Generated new persistent machine UUID: {new_uuid}")
    return new_uuid


def _write_uuid_file(value: str) -> None:
    """Atomically write the UUID file with restricted permissions."""
    try:
        _MACHINE_UUID_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = _MACHINE_UUID_FILE.with_suffix(".tmp")
        tmp.write_text(value + "\n", encoding="utf-8")
        # On Unix, set 0600; on Windows this is a no-op but harmless
        try:
            os.chmod(tmp, 0o600)
        except Exception:
            pass
        tmp.replace(_MACHINE_UUID_FILE)
    except Exception as e:
        logger.warning(f"Failed to persist machine UUID: {e}")
