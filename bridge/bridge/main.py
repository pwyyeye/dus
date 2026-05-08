from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

from loguru import logger

from bridge.config import load_config, BridgeConfig, detect_available_agents
from bridge.api_client import ApiClient
from bridge.executor import get_executor, AgentExecutor
from bridge.logger import setup_logger
from bridge.health import HealthServer
from bridge.gc import GCLoop
from bridge.identity import ensure_machine_uuid

REGISTER_RETRY_BASE = 2
REGISTER_RETRY_MAX = 60
CONSECUTIVE_401_THRESHOLD = 3


class Bridge:
    """Main bridge process: poll cloud, dispatch tasks to local agents.

    Each detected agent CLI is registered as an independent machine (device),
    so device granularity is at the agent CLI level — same as Multica's runtime model.
    """

    def __init__(self, config: BridgeConfig, available_agents: list[dict]):
        self.config = config
        self.api = ApiClient(config)
        self._available_agents = available_agents

        # One executor per detected agent CLI
        self._executors: dict[str, AgentExecutor] = {}
        self._agent_versions: dict[str, str] = {}
        for agent in available_agents:
            agent_type = agent["agent_type"]
            self._executors[agent_type] = get_executor(
                agent_type=agent_type,
                agent_path=agent["path"],
                timeout=config.agent.timeout,
            )
            self._agent_versions[agent_type] = agent.get("version", "unknown")

        self.semaphore = asyncio.Semaphore(config.max_concurrent_tasks)
        self._running = True
        self._running_tasks = 0
        self._agent_running_tasks: dict[str, int] = {}  # agent_type → count
        self._tasks: list[asyncio.Task] = []
        self._consecutive_401s = 0
        self._active_task_ids: set[str] = set()

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
            "agents": list(self._executors.keys()),
            "agent_versions": self._agent_versions,
            "active_task_count": self._running_tasks,
        }

    async def start(self):
        """Main entry: start health server, register machines, then poll loop."""
        agent_types = [a["agent_type"] for a in self._available_agents]
        logger.info(f"Bridge starting — machine_id={self.config.machine.machine_id}, "
                     f"agents={agent_types}, capability={self.config.machine.agent_capability}")

        # Start health server
        health_ok = await self.health.start()
        if not health_ok:
            logger.error("Health server failed to start. Another bridge may be running.")
            return

        # Register one machine per agent CLI
        await self._register_with_retry()
        registered = [at for at in self._executors if self.api.is_registered(at)]
        if not registered:
            logger.error("No agents registered successfully, exiting")
            return
        logger.info(f"Registered {len(registered)}/{len(self._executors)} agents: {registered}")

        # Start GC loop
        self.gc.start()

        logger.info(f"Polling every {self.config.cloud.poll_interval}s ...")
        while self._running:
            for agent_type in list(self._executors.keys()):
                if not self.api.is_registered(agent_type):
                    continue
                try:
                    tasks = await self.api.poll_tasks(agent_type)
                    for task in tasks:
                        task["_agent_type"] = agent_type
                        t = asyncio.create_task(self._handle_task_safe(task))
                        self._tasks.append(t)
                        t.add_done_callback(lambda _t: self._tasks.remove(_t) if _t in self._tasks else None)
                except Exception as e:
                    logger.error(f"Poll error for {agent_type}: {e}")

                # Update agent status per agent CLI
                agent_status = "busy" if self._agent_running_tasks.get(agent_type, 0) > 0 else "idle"
                await self.api.update_agent_status(agent_type, agent_status)

            # Check if we need to re-register (consecutive 401s)
            if self._consecutive_401s >= CONSECUTIVE_401_THRESHOLD:
                logger.warning(f"Consecutive {self._consecutive_401s} auth failures, re-registering...")
                await self._register_with_retry()

            await asyncio.sleep(self.config.cloud.poll_interval)

    async def _register_all(self) -> bool:
        """Register all unregistered agent CLIs. Returns True if at least one succeeds."""
        any_ok = False
        for agent in self._available_agents:
            agent_type = agent["agent_type"]
            if self.api.is_registered(agent_type):
                any_ok = True
                continue
            ok = await self.api.register_machine(
                agent_type=agent_type,
                agent_version=self._agent_versions.get(agent_type),
            )
            if ok:
                any_ok = True
            else:
                logger.warning(f"Failed to register {agent_type}")
        return any_ok

    async def _register_with_retry(self):
        """Register all agents with exponential backoff retry."""
        delay = REGISTER_RETRY_BASE
        while self._running:
            ok = await self._register_all()
            if ok:
                self._consecutive_401s = 0
                return
            logger.warning(f"Registration failed, retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, REGISTER_RETRY_MAX)

    async def _handle_task_safe(self, task: dict):
        """Handle task with concurrency limit and error safety."""
        agent_type = task.get("_agent_type", "unknown")
        async with self.semaphore:
            self._running_tasks += 1
            self._agent_running_tasks[agent_type] = self._agent_running_tasks.get(agent_type, 0) + 1
            task_name = task.get("task_id", task["id"])
            self._active_task_ids.add(task_name)
            try:
                await self._handle_task(task)
            except Exception as e:
                logger.error(f"Task {task_name} handler error: {e}")
            finally:
                self._running_tasks -= 1
                self._agent_running_tasks[agent_type] = max(0, self._agent_running_tasks.get(agent_type, 1) - 1)
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
        agent_type = task.get("_agent_type", "unknown")
        executor = self._executors.get(agent_type)
        if not executor:
            logger.error(f"Task {task_name}: no executor for agent_type={agent_type}")
            await self.api.update_task_status(task_id, "failed")
            return

        if capability == "manual_only":
            logger.info(f"Task {task_name}: manual_only → triggering reminder")
            await self.api.send_reminder(task_id)
            return

        # Remote execution
        logger.info(f"Task {task_name}: executing with {agent_type}")
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
        watcher = asyncio.create_task(self._watch_cancellation(task_id, cancel_event, executor))

        try:
            result = await executor.execute(
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

        if executor.was_cancelled():
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

    async def _watch_cancellation(self, task_id: str, cancel_event: asyncio.Event, executor: AgentExecutor):
        """Poll task status and cancel execution if the task is marked cancelled."""
        while not cancel_event.is_set():
            try:
                task = await self.api.get_task(task_id)
                if task and task.get("status") == "cancelled":
                    logger.info(f"Task {task_id}: cancellation detected, stopping executor...")
                    executor.cancel()
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

    # Detect all available agent CLIs on this machine
    available_agents = detect_available_agents()
    if not available_agents:
        print("ERROR: No agent CLI found on this machine.")
        print("Install at least one: claude, codex, hermes, openclaw, kimi-cli")
        sys.exit(1)

    # Print config summary on startup
    print("=" * 50)
    print("Bridge Configuration Summary")
    print("=" * 50)
    print(f"Machine ID:     {config.machine.machine_id}")
    print(f"Machine UUID:   {machine_uuid}")
    print(f"Machine Name:   {config.machine.machine_name}")
    print(f"Capability:     {config.machine.agent_capability}")
    print(f"Project ID:     {config.machine.project_id or '(none)'}")
    print(f"Cloud API URL:  {config.cloud.api_url}")
    print(f"Poll Interval:  {config.cloud.poll_interval}s")
    print(f"Timeout:        {config.agent.timeout}s")
    print(f"Health Port:    {config.health.port}")
    print(f"Max Concurrent: {config.max_concurrent_tasks}")
    print(f"GC Enabled:     {config.gc.enabled}")
    print(f"Log Level:      {config.logging.level}")
    print("-" * 50)
    print(f"Detected agents ({len(available_agents)}):")
    for a in available_agents:
        print(f"  {a['agent_type']}: {a['path']} (v{a['version']})")
    print("=" * 50)

    bridge = Bridge(config, available_agents)

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
