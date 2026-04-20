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

    async def start(self):
        """Main entry: register then poll loop."""
        logger.info(f"Bridge starting — machine_id={self.config.machine.machine_id}, "
                     f"agent_type={self.config.machine.agent_type}, "
                     f"capability={self.config.machine.agent_capability}")

        registered = await self.api.register_machine()
        if not registered:
            logger.error("Failed to register machine, exiting")
            return

        logger.info(f"Polling every {self.config.cloud.poll_interval}s ...")
        while self._running:
            try:
                tasks = await self.api.poll_tasks()
                for task in tasks:
                    asyncio.create_task(self._handle_task_safe(task))
            except Exception as e:
                logger.error(f"Poll loop error: {e}")

            await asyncio.sleep(self.config.cloud.poll_interval)

    async def _handle_task_safe(self, task: dict):
        """Handle task with concurrency limit and error safety."""
        async with self.semaphore:
            try:
                await self._handle_task(task)
            except Exception as e:
                logger.error(f"Task {task.get('task_id', '?')} handler error: {e}")

    async def _handle_task(self, task: dict):
        """Route task to executor or reminder based on agent_capability."""
        task_id = task["id"]
        task_name = task.get("task_id", task_id)
        capability = task.get("agent_capability", "remote_execution")
        instruction = task.get("instruction", "")

        if capability == "manual_only":
            logger.info(f"Task {task_name}: manual_only → triggering reminder")
            await self.api.trigger_reminder(task_id)
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

    def stop(self):
        logger.info("Shutting down bridge...")
        self._running = False

    async def cleanup(self):
        await self.api.close()


async def async_main():
    config = load_config()
    setup_logger(config.logging.level)

    bridge = Bridge(config)

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
