from __future__ import annotations

import asyncio
import os
import platform
import shutil
from pathlib import Path

from loguru import logger


class AgentExecutor:
    """Base class for Agent executors."""

    def __init__(self, agent_path: str, timeout: int = 3600):
        self.agent_path = agent_path
        self.timeout = timeout

    async def execute(self, instruction: str, workdir: str | None = None) -> dict:
        raise NotImplementedError


def _resolve_executable(path: str) -> tuple[str, bool]:
    """Resolve executable for cross-platform. On Windows, .CMD/.BAT need shell."""
    if platform.system() == "Windows":
        resolved = shutil.which(path)
        if resolved and resolved.lower().endswith((".cmd", ".bat")):
            return resolved, True
    return path, False


class ClaudeCodeExecutor(AgentExecutor):
    """Claude Code executor using --print mode."""

    async def execute(self, instruction: str, workdir: str | None = None) -> dict:
        logger.info(f"Executing Claude Code: {instruction[:100]}...")
        try:
            resolved_path, use_shell = _resolve_executable(self.agent_path)
            if use_shell:
                cmd = f'{resolved_path} --print "{instruction}"'
            else:
                cmd = (resolved_path, "--print", instruction)
            create_proc = (
                asyncio.create_subprocess_shell if use_shell
                else asyncio.create_subprocess_exec
            )
            proc = await create_proc(
                cmd,
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


class GenericAgentExecutor(AgentExecutor):
    """Generic agent executor for CLIs that accept instruction via stdin."""

    async def execute(self, instruction: str, workdir: str | None = None) -> dict:
        logger.info(f"Executing {self.agent_path}: {instruction[:100]}...")
        try:
            resolved_path, use_shell = _resolve_executable(self.agent_path)
            if use_shell:
                cmd = f'echo "{instruction}" | {resolved_path}'
            else:
                cmd = (resolved_path,)
                use_shell = False
            create_proc = (
                asyncio.create_subprocess_shell if use_shell
                else asyncio.create_subprocess_exec
            )
            proc = await create_proc(
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                env={**os.environ, "NO_COLOR": "1"},
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=instruction.encode()), timeout=self.timeout
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


class CodexExecutor(AgentExecutor):
    """OpenAI Codex CLI executor."""

    async def execute(self, instruction: str, workdir: str | None = None) -> dict:
        logger.info(f"Executing Codex CLI: {instruction[:100]}...")
        try:
            resolved_path, use_shell = _resolve_executable(self.agent_path)
            if use_shell:
                cmd = f'{resolved_path} --print "{instruction}"'
            else:
                cmd = (resolved_path, "--print", instruction)
            create_proc = (
                asyncio.create_subprocess_shell if use_shell
                else asyncio.create_subprocess_exec
            )
            proc = await create_proc(
                cmd,
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
        "codex": CodexExecutor,
        "hermes_agent": GenericAgentExecutor,
        "openclaw": GenericAgentExecutor,
    }
    cls = executors.get(agent_type, StubExecutor)
    return cls(agent_path=agent_path, timeout=timeout)
