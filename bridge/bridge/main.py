from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from bridge.config import load_config, BridgeConfig
from bridge.api_client import ApiClient
from bridge.executor import get_executor
from bridge.logger import setup_logger

MAX_CONCURRENT_TASKS = 3
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
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        self._running = True
        self._running_tasks = 0
        self._tasks: list[asyncio.Task] = []
        self._consecutive_401s = 0

    async def start(self):
        """Main entry: register then poll loop."""
        logger.info(f"Bridge starting — machine_id={self.config.machine.machine_id}, "
                     f"agent_type={self.config.machine.agent_type}, "
                     f"capability={self.config.machine.agent_capability}")

        await self._register_with_retry()
        if not self.api.machine_uuid:
            logger.error("Failed to register machine, exiting")
            return

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

    async def _register_with_retry(self):
        """Register with exponential backoff retry."""
        delay = REGISTER_RETRY_BASE
        while self._running:
            registered = await self.api.register_machine()
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
            try:
                await self._handle_task(task)
            except Exception as e:
                logger.error(f"Task {task.get('task_id', '?')} handler error: {e}")
            finally:
                self._running_tasks -= 1

    async def _handle_task(self, task: dict):
        """Route task to executor or reminder based on agent_capability."""
        task_id = task["id"]
        task_name = task.get("task_id", task_id)
        capability = task.get("agent_capability", "remote_execution")
        instruction = task.get("instruction", "")

        if capability == "manual_only":
            logger.info(f"Task {task_name}: manual_only → triggering reminder")
            await self.api.send_reminder(task_id)
            return

        # Remote execution
        logger.info(f"Task {task_name}: executing remotely")
        await self.api.update_task_status(task_id, "running")

        # Prepare workdir
        workdir = self.config.agent.workdir_template.format(task_id=task_name)
        Path(workdir).mkdir(parents=True, exist_ok=True)

        result = await self.executor.execute(instruction, workdir=workdir)
        logger.info(f"Task {task_name}: done (exit_code={result['exit_code']})")

        await self.api.submit_result(task_id, result)

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
        # Wait for running tasks to complete gracefully
        if self._tasks:
            logger.info(f"Waiting for {len(self._tasks)} task(s) to complete...")
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.api.close()


async def async_main():
    config = load_config()
    setup_logger(config.logging.level)

    # Print config summary on startup
    print("=" * 50)
    print("Bridge Configuration Summary")
    print("=" * 50)
    print(f"Machine ID:     {config.machine.machine_id}")
    print(f"Machine Name:   {config.machine.machine_name}")
    print(f"Agent Type:     {config.machine.agent_type}")
    print(f"Capability:     {config.machine.agent_capability}")
    print(f"Project ID:     {config.machine.project_id or '(none)'}")
    print(f"Cloud API URL:  {config.cloud.api_url}")
    print(f"Poll Interval:  {config.cloud.poll_interval}s")
    print(f"Agent Path:     {config.agent.path}")
    print(f"Timeout:        {config.agent.timeout}s")
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
