from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger


class AgentExecutor:
    """Base class for Agent executors."""

    def __init__(self, agent_path: str, timeout: int = 3600):
        self.agent_path = agent_path
        self.timeout = timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._cancelled = False

    async def execute(
        self,
        instruction: str,
        workdir: str | None = None,
        env_vars: dict[str, str] | None = None,
        prior_session_id: str | None = None,
        prior_work_dir: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
        agent_instructions: str | None = None,
        model: str | None = None,
        custom_args: list[str] | None = None,
        mcp_config: dict | None = None,
    ) -> dict:
        raise NotImplementedError

    async def get_version(self) -> str | None:
        """Detect CLI version by running --version."""
        try:
            resolved, _ = _resolve_executable(self.agent_path)
            proc = await asyncio.create_subprocess_exec(
                resolved, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            text = stdout.decode("utf-8", errors="replace").strip() or stderr.decode("utf-8", errors="replace").strip()
            return text.splitlines()[0] if text else None
        except Exception as e:
            logger.debug(f"Version detection failed: {e}")
            return None

    def cancel(self) -> bool:
        """Cancel the running agent process. Returns True if a process was killed."""
        if self._proc is None or self._proc.returncode is not None:
            return False
        try:
            self._proc.kill()
            self._cancelled = True
            logger.info("Agent process killed on cancel request")
            return True
        except ProcessLookupError:
            return False

    def was_cancelled(self) -> bool:
        return self._cancelled


def _resolve_executable(path: str) -> tuple[str, bool]:
    """Resolve executable for cross-platform. On Windows, .CMD/.BAT need shell."""
    if platform.system() == "Windows":
        resolved = shutil.which(path)
        if resolved and resolved.lower().endswith((".cmd", ".bat")):
            return resolved, True
    return path, False


def _build_env(env_vars: dict[str, str] | None) -> dict[str, str]:
    """Merge os.environ with injected env vars."""
    env = {**os.environ, "NO_COLOR": "1"}
    if env_vars:
        env.update(env_vars)
    return env


def _decode_output(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


async def _read_stream(
    stream: asyncio.StreamReader,
    lines: list[str],
    on_output: Callable[[str, str], None] | None,
    is_stderr: bool,
) -> None:
    """Read a stream line-by-line, accumulating and optionally calling on_output."""
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace")
        lines.append(text)
        if on_output:
            on_output("" if is_stderr else text, text if is_stderr else "")


class ClaudeCodeExecutor(AgentExecutor):
    """Claude Code executor using non-interactive auto-approve mode.

    Uses --print with --permission-mode bypassPermissions so Claude can
    execute bash commands and edit files without human interaction.
    This is the critical fix that makes remote execution actually useful.
    """

    async def execute(
        self,
        instruction: str,
        workdir: str | None = None,
        env_vars: dict[str, str] | None = None,
        prior_session_id: str | None = None,
        prior_work_dir: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
        agent_instructions: str | None = None,
        model: str | None = None,
        custom_args: list[str] | None = None,
        mcp_config: dict | None = None,
    ) -> dict:
        self._cancelled = False
        # Prepend agent instructions if provided
        effective_instruction = instruction
        if agent_instructions:
            effective_instruction = f"{agent_instructions}\n\n---\n\n{instruction}"
        logger.info(f"Executing Claude Code: {effective_instruction[:100]}...")
        effective_workdir = prior_work_dir or workdir
        if prior_work_dir:
            logger.info(f"Resuming prior work_dir: {prior_work_dir}")
        try:
            resolved_path, use_shell = _resolve_executable(self.agent_path)

            args = ["--print", "--permission-mode", "bypassPermissions"]
            if model:
                args.extend(["--model", model])
            if prior_session_id:
                args.extend(["--resume", prior_session_id])
            if custom_args:
                args.extend(custom_args)
            args.append(effective_instruction)

            if use_shell:
                arg_str = " ".join(f'"{a.replace(chr(34), chr(92)+chr(34))}"' for a in args)
                cmd = f'{resolved_path} {arg_str}'
                create_proc = asyncio.create_subprocess_shell
            else:
                cmd = (resolved_path, *args)
                create_proc = asyncio.create_subprocess_exec

            env = _build_env(env_vars)
            self._proc = await create_proc(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_workdir,
                env=env,
            )

            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            readers = asyncio.gather(
                _read_stream(self._proc.stdout, stdout_lines, on_output, False),
                _read_stream(self._proc.stderr, stderr_lines, on_output, True),
            )

            try:
                await asyncio.wait_for(readers, timeout=self.timeout)
            except asyncio.TimeoutError:
                try:
                    if self._proc:
                        self._proc.kill()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(readers, timeout=5.0)
                except asyncio.TimeoutError:
                    readers.cancel()
                    try:
                        await readers
                    except asyncio.CancelledError:
                        pass
                logger.warning("Execution timed out")
                return {"exit_code": -1, "stdout": "".join(stdout_lines), "stderr": "Execution timeout", "error_type": "timeout"}

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            return {
                "exit_code": self._proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "error_type": None if self._proc.returncode == 0 else "execution_error",
            }
        except FileNotFoundError:
            logger.error(f"Agent executable not found: {self.agent_path}")
            return {"exit_code": -1, "stdout": "", "stderr": f"Agent not found: {self.agent_path}", "error_type": "agent_not_found"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "error_type": "unexpected_error"}
        finally:
            self._proc = None


class GenericAgentExecutor(AgentExecutor):
    """Generic agent executor for CLIs that accept instruction via stdin."""

    async def execute(
        self,
        instruction: str,
        workdir: str | None = None,
        env_vars: dict[str, str] | None = None,
        prior_session_id: str | None = None,
        prior_work_dir: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
        agent_instructions: str | None = None,
        model: str | None = None,
        custom_args: list[str] | None = None,
        mcp_config: dict | None = None,
    ) -> dict:
        self._cancelled = False
        logger.info(f"Executing {self.agent_path}: {instruction[:100]}...")
        effective_workdir = prior_work_dir or workdir
        try:
            resolved_path, use_shell = _resolve_executable(self.agent_path)
            if use_shell:
                safe_instruction = instruction.replace('"', '\\"')
                cmd = f'echo "{safe_instruction}" | {resolved_path}'
                create_proc = asyncio.create_subprocess_shell
            else:
                cmd = (resolved_path,)
                create_proc = asyncio.create_subprocess_exec

            env = _build_env(env_vars)
            self._proc = await create_proc(
                cmd,
                stdin=asyncio.subprocess.PIPE if not use_shell else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_workdir,
                env=env,
            )

            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            readers = asyncio.gather(
                _read_stream(self._proc.stdout, stdout_lines, on_output, False),
                _read_stream(self._proc.stderr, stderr_lines, on_output, True),
            )

            try:
                if not use_shell:
                    self._proc.stdin.write(instruction.encode())
                    self._proc.stdin.close()
                await asyncio.wait_for(readers, timeout=self.timeout)
            except asyncio.TimeoutError:
                try:
                    if self._proc:
                        self._proc.kill()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(readers, timeout=5.0)
                except asyncio.TimeoutError:
                    readers.cancel()
                    try:
                        await readers
                    except asyncio.CancelledError:
                        pass
                logger.warning("Execution timed out")
                return {"exit_code": -1, "stdout": "".join(stdout_lines), "stderr": "Execution timeout", "error_type": "timeout"}

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            return {
                "exit_code": self._proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "error_type": None if self._proc.returncode == 0 else "execution_error",
            }
        except FileNotFoundError:
            logger.error(f"Agent executable not found: {self.agent_path}")
            return {"exit_code": -1, "stdout": "", "stderr": f"Agent not found: {self.agent_path}", "error_type": "agent_not_found"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "error_type": "unexpected_error"}
        finally:
            self._proc = None


class CodexExecutor(AgentExecutor):
    """OpenAI Codex CLI executor."""

    async def execute(
        self,
        instruction: str,
        workdir: str | None = None,
        env_vars: dict[str, str] | None = None,
        prior_session_id: str | None = None,
        prior_work_dir: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
        agent_instructions: str | None = None,
        model: str | None = None,
        custom_args: list[str] | None = None,
        mcp_config: dict | None = None,
    ) -> dict:
        self._cancelled = False
        logger.info(f"Executing Codex CLI: {instruction[:100]}...")
        effective_workdir = prior_work_dir or workdir
        try:
            resolved_path, use_shell = _resolve_executable(self.agent_path)
            if use_shell:
                cmd = f'{resolved_path} --print "{instruction.replace(chr(34), chr(92)+chr(34))}"'
                create_proc = asyncio.create_subprocess_shell
            else:
                cmd = (resolved_path, "--print", instruction)
                create_proc = asyncio.create_subprocess_exec

            env = _build_env(env_vars)
            self._proc = await create_proc(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_workdir,
                env=env,
            )

            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            readers = asyncio.gather(
                _read_stream(self._proc.stdout, stdout_lines, on_output, False),
                _read_stream(self._proc.stderr, stderr_lines, on_output, True),
            )

            try:
                await asyncio.wait_for(readers, timeout=self.timeout)
            except asyncio.TimeoutError:
                try:
                    if self._proc:
                        self._proc.kill()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(readers, timeout=5.0)
                except asyncio.TimeoutError:
                    readers.cancel()
                    try:
                        await readers
                    except asyncio.CancelledError:
                        pass
                logger.warning("Execution timed out")
                return {"exit_code": -1, "stdout": "".join(stdout_lines), "stderr": "Execution timeout", "error_type": "timeout"}

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            return {
                "exit_code": self._proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "error_type": None if self._proc.returncode == 0 else "execution_error",
            }
        except FileNotFoundError:
            logger.error(f"Agent executable not found: {self.agent_path}")
            return {"exit_code": -1, "stdout": "", "stderr": f"Agent not found: {self.agent_path}", "error_type": "agent_not_found"}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "error_type": "unexpected_error"}
        finally:
            self._proc = None


class StubExecutor(AgentExecutor):
    """Stub executor for agents that have not been verified yet."""

    async def execute(
        self,
        instruction: str,
        workdir: str | None = None,
        env_vars: dict[str, str] | None = None,
        prior_session_id: str | None = None,
        prior_work_dir: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
        agent_instructions: str | None = None,
        model: str | None = None,
        custom_args: list[str] | None = None,
        mcp_config: dict | None = None,
    ) -> dict:
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
        "kimi": GenericAgentExecutor,
    }
    cls = executors.get(agent_type, StubExecutor)
    return cls(agent_path=agent_path, timeout=timeout)
