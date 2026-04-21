"""Tests for ClaudeCodeExecutor using mocked subprocess."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bridge"))

from bridge.executor import ClaudeCodeExecutor, StubExecutor, get_executor


class TestClaudeCodeExecutor:
    """Tests for ClaudeCodeExecutor return structure."""

    @pytest.mark.asyncio
    async def test_execute_success_returns_correct_structure(self):
        """Test successful execution returns expected dict structure."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"stdout content", b"stderr content"))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()

        executor = ClaudeCodeExecutor(agent_path="claude", timeout=3600)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await executor.execute("test instruction", workdir="/tmp/test")

        assert isinstance(result, dict)
        assert "exit_code" in result
        assert "stdout" in result
        assert "stderr" in result
        assert "error_type" in result

        assert result["exit_code"] == 0
        assert result["stdout"] == "stdout content"
        assert result["stderr"] == "stderr content"
        assert result["error_type"] is None

    @pytest.mark.asyncio
    async def test_execute_failure_returns_correct_structure(self):
        """Test failed execution returns expected dict structure with error_type."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error message"))
        mock_proc.returncode = 1
        mock_proc.kill = MagicMock()

        executor = ClaudeCodeExecutor(agent_path="claude", timeout=3600)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await executor.execute("test instruction", workdir="/tmp/test")

        assert isinstance(result, dict)
        assert "exit_code" in result
        assert "stdout" in result
        assert "stderr" in result
        assert "error_type" in result

        assert result["exit_code"] == 1
        assert result["stdout"] == ""
        assert result["stderr"] == "error message"
        assert result["error_type"] == "execution_error"

    @pytest.mark.asyncio
    async def test_execute_timeout_returns_correct_structure(self):
        """Test timeout returns expected dict structure with error_type timeout."""
        mock_proc = AsyncMock()
        # First communicate() raises TimeoutError (simulating wait_for timeout)
        # Second communicate() (after kill) returns normally
        mock_proc.communicate = AsyncMock(side_effect=[asyncio.TimeoutError, (b"", b"")])
        mock_proc.kill = MagicMock()

        executor = ClaudeCodeExecutor(agent_path="claude", timeout=3600)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await executor.execute("test instruction", workdir="/tmp/test")

        assert isinstance(result, dict)
        assert "exit_code" in result
        assert "stdout" in result
        assert "stderr" in result
        assert "error_type" in result

        assert result["exit_code"] == -1
        assert result["stdout"] == ""
        assert result["stderr"] == "Execution timeout"
        assert result["error_type"] == "timeout"

        # Verify proc.kill was called
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_not_found_returns_correct_structure(self):
        """Test file not found returns expected dict structure with error_type agent_not_found."""
        executor = ClaudeCodeExecutor(agent_path="nonexistent_agent", timeout=3600)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("Agent executable not found: nonexistent_agent")):
            result = await executor.execute("test instruction", workdir="/tmp/test")

        assert isinstance(result, dict)
        assert "exit_code" in result
        assert "stdout" in result
        assert "stderr" in result
        assert "error_type" in result

        assert result["exit_code"] == -1
        assert result["stdout"] == ""
        assert "Agent not found" in result["stderr"]
        assert result["error_type"] == "agent_not_found"

    @pytest.mark.asyncio
    async def test_execute_includes_instruction_in_metadata(self):
        """Test execution logs instruction (verifies instruction is passed through)."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"stdout", b""))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()

        executor = ClaudeCodeExecutor(agent_path="claude", timeout=3600)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await executor.execute("Say hello", workdir="/tmp/test")

            # Verify create_subprocess_exec was called with the instruction
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            # The instruction is passed as the third argument
            assert "Say hello" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_passes_workdir_to_subprocess(self):
        """Test execution passes workdir to subprocess correctly."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()

        executor = ClaudeCodeExecutor(agent_path="claude", timeout=3600)
        workdir = "/tmp/custom/workdir"

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await executor.execute("test", workdir=workdir)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("cwd") == workdir

    @pytest.mark.asyncio
    async def test_execute_sets_no_color_env(self):
        """Test execution sets NO_COLOR environment variable."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()

        executor = ClaudeCodeExecutor(agent_path="claude", timeout=3600)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            await executor.execute("test", workdir=None)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            env = call_kwargs.get("env", {})
            assert "NO_COLOR" in env
            assert env["NO_COLOR"] == "1"


class TestStubExecutor:
    """Tests for StubExecutor return structure."""

    @pytest.mark.asyncio
    async def test_stub_executor_returns_correct_structure(self):
        """Test StubExecutor returns expected dict structure."""
        executor = StubExecutor(agent_path="unverified_agent", timeout=3600)
        result = await executor.execute("test instruction", workdir="/tmp/test")

        assert isinstance(result, dict)
        assert "exit_code" in result
        assert "stdout" in result
        assert "stderr" in result
        assert "error_type" in result

        assert result["exit_code"] == -1
        assert result["stdout"] == ""
        assert result["error_type"] == "not_verified"
        assert "unverified_agent" in result["stderr"]


class TestGetExecutor:
    """Tests for get_executor factory function."""

    def test_get_executor_returns_claude_code_executor(self):
        """Test get_executor returns ClaudeCodeExecutor for claude_code."""
        executor = get_executor("claude_code", "claude", timeout=3600)
        assert isinstance(executor, ClaudeCodeExecutor)
        assert executor.agent_path == "claude"
        assert executor.timeout == 3600

    def test_get_executor_returns_stub_for_unknown_agent(self):
        """Test get_executor returns StubExecutor for unknown agent types."""
        executor = get_executor("unknown_agent", "some_agent", timeout=3600)
        assert isinstance(executor, StubExecutor)
        assert executor.agent_path == "some_agent"

    def test_get_executor_passes_timeout_correctly(self):
        """Test get_executor passes timeout to executor."""
        executor = get_executor("claude_code", "claude", timeout=7200)
        assert executor.timeout == 7200
