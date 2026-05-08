from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

from loguru import logger

from bridge.config import load_config, BridgeConfig, detect_available_agents
from bridge.api_client import ApiClient
from bridge.executor import get_executor
from bridge.logger import setup_logger
from bridge.health import HealthServer
from bridge.gc import GCLoop
from bridge.identity import ensure_machine_uuid

REGISTER_RETRY_BASE = 2
REGISTER_RETRY_MAX = 60
CONSECUTIVE_401_THRESHOLD = 3


class Bridge:
    """Main bridge process: poll cloud, dispatch tasks to local agent."""

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.api = ApiClient(config)
        self.executor = get_executor(
            agent_type=config.machine.agent_type,
            agent_path=config.agent.path,
            timeout=config.agent.timeout,
        )
        self.semaphore = asyncio.Semaphore(config.max_concurrent_tasks)
        self._running = True
        self._running_tasks = 0
        self._tasks: list[asyncio.Task] = []
        self._consecutive_401s = 0
        self._active_task_ids: set[str] = set()
        self._agent_version = "unknown"
        self._available_agents: list[dict] = []

        # Health server
        self.health = HealthServer(
            health_port=config.health.port,
            get_status=self._health_status,
            on_shutdown=self.stop,
        )

        # GC loop
        self.gc = GCLoop(
            workdir_template=config.agent.workdir_template,
            get_active_task_ids=lambda: self._active_task_ids.copy(),
            gc_enabled=config.gc.enabled,
            gc_interval=config.gc.interval,
            gc_ttl=config.gc.ttl,
        )

    def _health_status(self) -> dict:
        """Return current status for /health endpoint."""
        return {
            "machine_id": self.config.machine.machine_id,
            "agent_type": self.config.machine.agent_type,
            "active_task_count": self._running_tasks,
            "agent_version": self._agent_version or "unknown",
        }

    async def start(self):
        """Main entry: start health server, register, then poll loop."""
        logger.info(f"Bridge starting — machine_id={self.config.machine.machine_id}, "
                     f"agent_type={self.config.machine.agent_type}, "
                     f"capability={self.config.machine.agent_capability}")

        # Start health server
        health_ok = await self.health.start()
        if not health_ok:
            logger.error("Health server failed to start. Another bridge may be running.")
            return

        # Detect local agent info before registering
        self._agent_version = await self.executor.get_version() or "unknown"
        if self._agent_version != "unknown":
            logger.info(f"Agent version: {self._agent_version}")
        self._available_agents = detect_available_agents()
        if self._available_agents:
            logger.info(f"Available agents: {[a['agent_type'] for a in self._available_agents]}")

        # Register machine (with agent info)
        await self._register_with_retry(
            agent_version=self._agent_version,
            available_agents=self._available_agents,
        )
        if not self.api.machine_uuid:
            logger.error("Failed to register machine, exiting")
            return

        # Start GC loop
        self.gc.start()

        logger.info(f"Polling every {self.config.cloud.poll_interval}s ...")
        while self._running:
            try:
                tasks = await self.api.poll_tasks()
                for task in tasks:
                    t = asyncio.create_task(self._handle_task_safe(task))
                    self._tasks.append(t)
                    t.add_done_callback(lambda _t: self._tasks.remove(_t) if _t in self._tasks else None)
            except Exception as e:
                logger.error(f"Poll loop error: {e}")

            # Update agent status based on running tasks
            agent_status = "busy" if self._running_tasks > 0 else "idle"
            await self.api.update_agent_status(agent_status)

            # Check if we need to re-register (consecutive 401s)
            if self._consecutive_401s >= CONSECUTIVE_401_THRESHOLD:
                logger.warning(f"Consecutive {self._consecutive_401s} auth failures, re-registering...")
                self.api.machine_uuid = None
                await self._register_with_retry()
                if not self.api.machine_uuid:
                    logger.warning("Re-registration failed, will retry on next cycle")

            await asyncio.sleep(self.config.cloud.poll_interval)

    async def _register_with_retry(self, agent_version: str | None = None, available_agents: list[dict] | None = None):
        """Register with exponential backoff retry."""
        delay = REGISTER_RETRY_BASE
        while self._running:
            registered = await self.api.register_machine(
                agent_version=agent_version,
                available_agents=available_agents,
            )
            if registered:
                self._consecutive_401s = 0
                return
            logger.warning(f"Registration failed, retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, REGISTER_RETRY_MAX)

    async def _handle_task_safe(self, task: dict):
        """Handle task with concurrency limit and error safety."""
        async with self.semaphore:
            self._running_tasks += 1
            task_name = task.get("task_id", task["id"])
            self._active_task_ids.add(task_name)
            try:
                await self._handle_task(task)
            except Exception as e:
                logger.error(f"Task {task_name} handler error: {e}")
            finally:
                self._running_tasks -= 1
                self._active_task_ids.discard(task_name)

    async def _handle_task(self, task: dict):
        """Route task to executor or reminder based on agent_capability.
        Supports session resumption via prior_session_id / prior_work_dir (Multica-inspired).
        """
        task_id = task["id"]
        task_name = task.get("task_id", task_id)
        capability = task.get("agent_capability", "remote_execution")
        instruction = task.get("instruction", "")
        prior_session_id = task.get("prior_session_id")
        prior_work_dir = task.get("prior_work_dir")

        if capability == "manual_only":
            logger.info(f"Task {task_name}: manual_only → triggering reminder")
            await self.api.send_reminder(task_id)
            return

        # Remote execution
        logger.info(f"Task {task_name}: executing remotely")
        if prior_session_id or prior_work_dir:
            logger.info(f"Task {task_name}: resuming session_id={prior_session_id}, work_dir={prior_work_dir}")
        await self.api.update_task_status(task_id, "running")

        # Prepare workdir (prefer prior work_dir for session resumption)
        if prior_work_dir:
            workdir = prior_work_dir
            Path(workdir).mkdir(parents=True, exist_ok=True)
        else:
            workdir = self.config.agent.workdir_template.format(task_id=task_name)
            Path(workdir).mkdir(parents=True, exist_ok=True)

        # Build env vars for the agent (Multica-inspired)
        env_vars = {
            "DUS_TOKEN": self.config.cloud.api_key,
            "DUS_API_URL": self.config.cloud.api_url,
            "DUS_MACHINE_ID": self.config.machine.machine_id,
            "DUS_TASK_ID": task_name,
        }

        # Progress buffering: accumulate output and flush every 2 seconds
        stdout_buffer: list[str] = []
        stderr_buffer: list[str] = []
        progress_stop = asyncio.Event()

        def on_output(stdout_chunk: str, stderr_chunk: str) -> None:
            if stdout_chunk:
                stdout_buffer.append(stdout_chunk)
            if stderr_chunk:
                stderr_buffer.append(stderr_chunk)

        async def _progress_flusher() -> None:
            while not progress_stop.is_set():
                try:
                    await asyncio.wait_for(progress_stop.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
                if stdout_buffer or stderr_buffer:
                    out = "".join(stdout_buffer)
                    err = "".join(stderr_buffer)
                    stdout_buffer.clear()
                    stderr_buffer.clear()
                    try:
                        await self.api.submit_progress(task_id, out, err)
                    except Exception as e:
                        logger.debug(f"Progress submit error for {task_name}: {e}")

        flusher = asyncio.create_task(_progress_flusher())

        # Start execution with cancellation watcher
        cancel_event = asyncio.Event()
        watcher = asyncio.create_task(self._watch_cancellation(task_id, cancel_event))

        try:
            result = await self.executor.execute(
                instruction,
                workdir=workdir,
                env_vars=env_vars,
                prior_session_id=prior_session_id,
                prior_work_dir=prior_work_dir,
                on_output=on_output,
            )
        finally:
            progress_stop.set()
            # Final flush of any remaining output
            if stdout_buffer or stderr_buffer:
                out = "".join(stdout_buffer)
                err = "".join(stderr_buffer)
                stdout_buffer.clear()
                stderr_buffer.clear()
                try:
                    await self.api.submit_progress(task_id, out, err)
                except Exception as e:
                    logger.debug(f"Final progress submit error for {task_name}: {e}")
            if not flusher.done():
                flusher.cancel()
                try:
                    await flusher
                except asyncio.CancelledError:
                    pass
            cancel_event.set()
            if not watcher.done():
                watcher.cancel()
                try:
                    await watcher
                except asyncio.CancelledError:
                    pass

        if self.executor.was_cancelled():
            logger.info(f"Task {task_name}: was cancelled, skipping result submission")
            await self.api.update_task_status(task_id, "cancelled")
            GCLoop.write_meta(workdir, task_name, "cancelled")
            return

        # Include session/work_dir for resumption on next run
        result_with_session = {
            **result,
            "work_dir": workdir,
        }

        logger.info(f"Task {task_name}: done (exit_code={result['exit_code']})")
        await self.api.submit_result(task_id, result_with_session)
        GCLoop.write_meta(workdir, task_name, "completed" if result.get("error_type") is None else "failed")

    async def _watch_cancellation(self, task_id: str, cancel_event: asyncio.Event):
        """Poll task status and cancel execution if the task is marked cancelled."""
        while not cancel_event.is_set():
            try:
                task = await self.api.get_task(task_id)
                if task and task.get("status") == "cancelled":
                    logger.info(f"Task {task_id}: cancellation detected, stopping executor...")
                    self.executor.cancel()
                    return
            except Exception as e:
                logger.debug(f"Cancellation poll error for task {task_id}: {e}")
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

    def track_auth_failure(self, status_code: int | None):
        """Track consecutive 401s for re-registration trigger."""
        if status_code == 401:
            self._consecutive_401s += 1
        else:
            self._consecutive_401s = 0

    def stop(self):
        logger.info("Shutting down bridge...")
        self._running = False

    async def cleanup(self):
        self.gc.stop()
        await self.health.stop()
        # Wait for running tasks to complete gracefully
        if self._tasks:
            logger.info(f"Waiting for {len(self._tasks)} task(s) to complete...")
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.api.close()


async def async_main():
    config = load_config()
    setup_logger(config.logging.level)

    # Ensure stable machine UUID (Multica-inspired identity persistence)
    machine_uuid = ensure_machine_uuid(config.machine.machine_id)
    os.environ["DUS_MACHINE_UUID"] = machine_uuid

    # Print config summary on startup
    print("=" * 50)
    print("Bridge Configuration Summary")
    print("=" * 50)
    print(f"Machine ID:     {config.machine.machine_id}")
    print(f"Machine UUID:   {machine_uuid}")
    print(f"Machine Name:   {config.machine.machine_name}")
    print(f"Agent Type:     {config.machine.agent_type}")
    print(f"Capability:     {config.machine.agent_capability}")
    print(f"Project ID:     {config.machine.project_id or '(none)'}")
    print(f"Cloud API URL:  {config.cloud.api_url}")
    print(f"Poll Interval:  {config.cloud.poll_interval}s")
    print(f"Agent Path:     {config.agent.path}")
    print(f"Timeout:        {config.agent.timeout}s")
    print(f"Health Port:    {config.health.port}")
    print(f"Max Concurrent: {config.max_concurrent_tasks}")
    print(f"GC Enabled:     {config.gc.enabled}")
    print(f"Log Level:      {config.logging.level}")
    print("=" * 50)

    bridge = Bridge(config)

    # Signal handlers: not available on Windows, use keyboard-only Ctrl+C
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, bridge.stop)

    try:
        await bridge.start()
    finally:
        await bridge.cleanup()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
