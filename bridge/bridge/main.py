from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

from loguru import logger

from bridge.config import load_config, BridgeConfig, detect_available_agents, save_api_key
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

    One device = one Machine record. All detected agent CLIs are reported
    in available_agents; tasks are dispatched to the first available executor.
    """

    def __init__(self, config: BridgeConfig, available_agents: list[dict], machine_id: str):
        self.config = config
        self.api = ApiClient(config)
        self._available_agents = available_agents
        self._machine_id = machine_id

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
        """Main entry: start health server, register device, then poll loop."""
        agent_types = [a["agent_type"] for a in self._available_agents]
        logger.info(f"Bridge starting — machine_id={self.config.machine.machine_id}, "
                     f"agents={agent_types}, capability={self.config.machine.agent_capability}")

        # Start health server
        health_ok = await self.health.start()
        if not health_ok:
            logger.error("Health server failed to start. Another bridge may be running.")
            return

        # Register this device as a single machine with all agents
        await self._register_with_retry()
        if not self.api.is_registered:
            logger.error("Machine registration failed, exiting")
            return
        logger.info(f"Device registered with {len(self._executors)} agents: {agent_types}")

        # Start GC loop
        self.gc.start()

        # Recover orphan tasks stuck in dispatched/running state
        try:
            recover_result = await self.api.recover_orphan_tasks()
            if recover_result and recover_result.get("recovered_count", 0) > 0:
                logger.info(f"Recovered {recover_result['recovered_count']} orphan tasks: {recover_result.get('orphans', [])}")
        except Exception as e:
            logger.warning(f"Orphan recovery failed (non-fatal): {e}")

        logger.info(f"Polling every {self.config.cloud.poll_interval}s ...")
        while self._running:
            try:
                tasks = await self.api.poll_tasks()
                for task in tasks:
                    t = asyncio.create_task(self._handle_task_safe(task))
                    self._tasks.append(t)
                    t.add_done_callback(lambda _t: self._tasks.remove(_t) if _t in self._tasks else None)
            except Exception as e:
                logger.error(f"Poll error: {e}")

            # Check if we need to re-register (consecutive 401s)
            if self._consecutive_401s >= CONSECUTIVE_401_THRESHOLD:
                logger.warning(f"Consecutive {self._consecutive_401s} auth failures, re-registering...")
                await self._register_with_retry()

            await asyncio.sleep(self.config.cloud.poll_interval)

    async def _register_all(self) -> bool:
        """Register this device as a single machine with all detected agents."""
        if self.api.is_registered:
            return True
        first_agent = self._available_agents[0]

        # Try authenticated endpoint first
        ok = await self.api.register_machine(
            machine_id=self._machine_id,
            machine_name=self.config.machine.machine_name,
            agent_type=first_agent["agent_type"],
            agent_version=self._agent_versions.get(first_agent["agent_type"]),
            available_agents=self._available_agents,
        )
        if ok:
            return True

        # Fallback: public registration (no auth required, generates new key)
        logger.warning("Authenticated register failed, trying public registration...")
        result = await self.api.register_and_get_key(
            machine_id=self._machine_id,
            machine_name=self.config.machine.machine_name,
            agent_type=first_agent["agent_type"],
            agent_capability=self.config.machine.agent_capability,
            agent_version=self._agent_versions.get(first_agent["agent_type"]),
            project_id=self.config.machine.project_id,
            project_root=self.config.machine.project_root,
            available_agents=self._available_agents,
        )
        if result:
            api_key, machine_uuid = result
            config_path = os.getenv("DUS_CONFIG_PATH", "config.yaml")
            save_api_key(config_path, api_key)
            self.config.cloud.api_key = api_key
            self.api = ApiClient(self.config)
            self.api._machine_uuid = machine_uuid
            logger.info(f"Re-registered via public endpoint, new API key saved")
            return True
        return False

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
        agent_config = task.get("agent_config")
        if agent_config and agent_config.get("agent_type"):
            agent_type = agent_config["agent_type"]
        else:
            agent_type = self._available_agents[0]["agent_type"]
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
        project_root_path = task.get("project_root_path")
        # Route: priority is agent_cli_id > agent_config.agent_type > first available CLI
        agent_config = task.get("agent_config")
        agent_cli_id = task.get("agent_cli_id")
        if agent_cli_id and agent_cli_id in self._executors:
            agent_type = agent_cli_id
        elif agent_config and agent_config.get("agent_type") and agent_config["agent_type"] in self._executors:
            agent_type = agent_config["agent_type"]
        else:
            agent_type = self._available_agents[0]["agent_type"]
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
        if agent_config:
            logger.info(f"Task {task_name}: executing with agent '{agent_config.get('name', 'unknown')}' ({agent_type})")
        else:
            logger.info(f"Task {task_name}: executing with {agent_type}")
        if prior_session_id or prior_work_dir:
            logger.info(f"Task {task_name}: resuming session_id={prior_session_id}, work_dir={prior_work_dir}")
        elif project_root_path:
            logger.info(f"Task {task_name}: using project_root_path={project_root_path}")

        # Notify server that task has started (for crash recovery tracking)
        await self.api.start_task(task_id)

        # Prepare workdir (prefer prior work_dir for session resumption, then project root)
        if prior_work_dir:
            workdir = prior_work_dir
            Path(workdir).mkdir(parents=True, exist_ok=True)
        elif project_root_path:
            workdir = project_root_path
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
        # Merge agent custom_env if present
        if agent_config and agent_config.get("custom_env"):
            env_vars.update(agent_config["custom_env"])

        # Extract agent execution params
        agent_instructions = agent_config.get("instructions") if agent_config else None
        agent_model = agent_config.get("model") if agent_config else None
        agent_custom_args = agent_config.get("custom_args") if agent_config else None
        agent_mcp_config = agent_config.get("mcp_config") if agent_config else None

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
                agent_instructions=agent_instructions,
                model=agent_model,
                custom_args=agent_custom_args,
                mcp_config=agent_mcp_config,
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
        # Ensure exit_code is always an int (proc.returncode can be None)
        if result.get("exit_code") is None:
            result["exit_code"] = -1
        result_with_session = {
            **result,
            "work_dir": workdir,
        }

        logger.info(f"Task {task_name}: done (exit_code={result['exit_code']})")
        await self.api.submit_result(task_id, result_with_session)
        GCLoop.write_meta(workdir, task_name, "completed" if result.get("error_type") is None else "failed")

    async def _watch_cancellation(self, task_id: str, cancel_event: asyncio.Event, executor: AgentExecutor):
        """Poll task status and cancel execution if the task is marked cancelled.
        Also serves as a heartbeat to keep the task alive on the server.
        """
        heartbeat_interval = 30  # seconds - heartbeat to server
        while not cancel_event.is_set():
            try:
                task = await self.api.get_task(task_id)
                if task and task.get("status") == "cancelled":
                    logger.info(f"Task {task_id}: cancellation detected, stopping executor...")
                    executor.cancel()
                    return
                # Heartbeat: submit progress to signal task is still alive
                await self.api.submit_progress(task_id, "", "")
            except Exception as e:
                logger.debug(f"Cancellation poll error for task {task_id}: {e}")
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=heartbeat_interval)
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
    # Force UTF-8 stdout on Windows to avoid garbled output
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
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

    # Auto-register: if no API key configured, call the public /register endpoint
    # to get one from the server. Use device fingerprint as machine_id.
    if not config.cloud.api_key:
        print("No API key configured — auto-registering with server...")
        tmp_client = ApiClient(config)
        first_agent = available_agents[0]
        reg_result = await tmp_client.register_and_get_key(
            machine_id=machine_uuid,
            machine_name=config.machine.machine_name,
            agent_type=first_agent["agent_type"],
            agent_capability=config.machine.agent_capability,
            agent_version=first_agent.get("version"),
            project_id=config.machine.project_id,
            project_root=config.machine.project_root,
            available_agents=available_agents,
        )
        await tmp_client.close()

        if not reg_result:
            print("ERROR: Auto-registration failed. Set cloud.api_key manually or check server.")
            sys.exit(1)
        api_key, registered_machine_uuid = reg_result

        # Save key to config.yaml and update in-memory config
        config_path = os.getenv("DUS_CONFIG_PATH", "config.yaml")
        save_api_key(config_path, api_key)
        config.cloud.api_key = api_key
        print(f"API key saved to {config_path}")

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

    bridge = Bridge(config, available_agents, machine_id=machine_uuid)

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
