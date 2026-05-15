from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from loguru import logger


class GCLoop:
    """Periodic workspace garbage collector.

    Inspired by Multica's GC loop:
    - Scans task workdirs and removes stale ones
    - Protects active (running) task directories
    - Writes .gc_meta.json on task completion for TTL tracking
    """

    def __init__(
        self,
        workdir_template: str,
        get_active_task_ids: Callable[[], set[str]],
        gc_enabled: bool = True,
        gc_interval: int = 3600,
        gc_ttl: int = 86400,
    ):
        self.workdir_template = workdir_template
        self.get_active_task_ids = get_active_task_ids
        self.gc_enabled = gc_enabled
        self.gc_interval = gc_interval
        self.gc_ttl = gc_ttl
        self._running = False
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self):
        """Start the GC loop as a background task."""
        if not self.gc_enabled:
            logger.info("GC: disabled")
            return
        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info(f"GC: started (interval={self.gc_interval}s, ttl={self.gc_ttl}s)")

    def stop(self):
        """Stop the GC loop."""
        self._running = False
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()

    async def _loop(self):
        """Run GC periodically."""
        # Delay first run so bridge finishes initializing
        try:
            await asyncio.wait_for(self._wait_for_stop(), timeout=30.0)
            return
        except asyncio.TimeoutError:
            pass

        self._run_once()

        while self._running:
            try:
                await asyncio.wait_for(self._wait_for_stop(), timeout=self.gc_interval)
                return
            except asyncio.TimeoutError:
                pass
            self._run_once()

    async def _wait_for_stop(self):
        """Block until stop is requested."""
        await self._stop_event.wait()

    def _run_once(self):
        """Perform one GC scan."""
        try:
            base_dir = self._extract_base_dir()
            if not base_dir or not base_dir.exists():
                return

            active_ids = self.get_active_task_ids()
            cleaned = 0
            skipped = 0

            for entry in base_dir.iterdir():
                if not entry.is_dir():
                    continue
                task_id = entry.name
                # Skip active tasks
                if task_id in active_ids:
                    skipped += 1
                    continue

                meta_path = entry / ".gc_meta.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        completed_at_str = meta.get("completed_at")
                        if completed_at_str:
                            completed_at = datetime.fromisoformat(completed_at_str)
                            age = (datetime.now(timezone.utc) - completed_at).total_seconds()
                            if age < self.gc_ttl:
                                skipped += 1
                                continue
                    except Exception as e:
                        logger.debug(f"GC: failed to parse meta for {entry}: {e}")
                else:
                    # No meta: check directory mtime as fallback
                    try:
                        mtime = entry.stat().st_mtime
                        age = time.time() - mtime
                        if age < self.gc_ttl:
                            skipped += 1
                            continue
                    except Exception as e:
                        logger.debug(f"GC: failed to stat {entry}: {e}")
                        continue

                # Eligible for cleanup
                try:
                    import shutil
                    await asyncio.to_thread(shutil.rmtree, entry)
                    cleaned += 1
                    logger.info(f"GC: removed stale workdir {entry}")
                except Exception as e:
                    logger.warning(f"GC: failed to remove {entry}: {e}")

            if cleaned > 0:
                logger.info(f"GC: cycle complete (cleaned={cleaned}, skipped={skipped})")
        except Exception as e:
            logger.warning(f"GC: cycle error: {e}")

    def _extract_base_dir(self) -> Path | None:
        """Extract the base directory from workdir_template."""
        # e.g. '/tmp/dus_task_{task_id}' -> '/tmp'
        template = self.workdir_template
        if "{task_id}" in template:
            base = template.split("{task_id}")[0]
            base = base.rstrip("/_")
            return Path(base) if base else None
        return None

    @staticmethod
    def write_meta(workdir: str, task_id: str, status: str):
        """Write GC metadata for a completed task."""
        meta_path = Path(workdir) / ".gc_meta.json"
        try:
            meta = {
                "task_id": task_id,
                "status": status,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.debug(f"GC: failed to write meta for {workdir}: {e}")
