from __future__ import annotations

import asyncio
import os
from pathlib import Path

from loguru import logger


class AgentExecutor:
    """Base class for Agent executors."""

    def __init__(self, agent_path: str, timeout: int = 3600):
        self.agent_path = agent_path
        self.timeout = timeout

    async def execute(self, instruction: str, workdir: str | None = None) -> dict:
        raise NotImplementedError


class ClaudeCodeExecutor(AgentExecutor):
    """Claude Code executor using --print mode."""

    async def execute(self, instruction: str, workdir: str | None = None) -> dict:
        logger.info(f"Executing Claude Code: {instruction[:100]}...")
        try:
            proc = await asyncio.create_subprocess_exec(
                self.agent_path, "--print", instruction,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                env={**os.environ, "NO_COLOR": "1"},
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                logger.warning("Execution timed out")
                return {"exit_code": -1, "stdout": "", "stderr": "Execution timeout", "error_type": "timeout"}

            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "error_type": None if proc.returncode == 0 else "execution_error",
            }
        except FileNotFoundError:
            logger.error(f"Agent executable not found: {self.agent_path}")
            return {"exit_code": -1, "stdout": "", "stderr": f"Agent not found: {self.agent_path}", "error_type": "agent_not_found"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "error_type": "unexpected_error"}


class StubExecutor(AgentExecutor):
    """Stub executor for agents that have not been verified yet."""

    async def execute(self, instruction: str, workdir: str | None = None) -> dict:
        logger.warning(f"StubExecutor: agent '{self.agent_path}' CLI not verified. Instruction: {instruction[:100]}")
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Agent '{self.agent_path}' CLI interface not yet verified. Please complete T0-1 smoke test.",
            "error_type": "not_verified",
        }


def get_executor(agent_type: str, agent_path: str, timeout: int = 3600) -> AgentExecutor:
    """Factory: return the appropriate executor for the agent type."""
    executors = {
        "claude_code": ClaudeCodeExecutor,
    }
    cls = executors.get(agent_type, StubExecutor)
    return cls(agent_path=agent_path, timeout=timeout)
