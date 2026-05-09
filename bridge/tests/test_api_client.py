"""Tests for bridge API client retry logic and multi-agent methods."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bridge"))

from bridge.api_client import ApiClient, MAX_RETRIES, RETRY_DELAY
from bridge.config import BridgeConfig, MachineConfig, CloudConfig


def create_test_config():
    """Create a test configuration."""
    return BridgeConfig(
        machine=MachineConfig(
            machine_id="test-machine-001",
            machine_name="Test Machine",
            agent_capability="remote_execution",
            project_id="test-project",
        ),
        cloud=CloudConfig(
            api_url="http://localhost:8000/api/v1",
            api_key="test-api-key-12345",
            poll_interval=60,
        ),
    )


class TestApiClientRetryLogic:
    """Tests for API client retry logic."""

    @pytest.mark.asyncio
    async def test_successful_request_returns_data(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True, "data": {"id": "123"}})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client._request("POST", "/machines", json={"test": "data"})

        assert result == {"success": True, "data": {"id": "123"}}
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_connect_error(self):
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=[
                httpx.ConnectError("Connection failed"),
                httpx.ConnectError("Connection failed"),
                MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(return_value={"success": True})
                ),
            ]
        )
        client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client._request("GET", "/test")

        assert result == {"success": True}
        assert mock_client.request.call_count == 3
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_read_timeout(self):
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=[
                httpx.ReadTimeout("Read timed out"),
                httpx.ReadTimeout("Read timed out"),
                MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(return_value={"success": True})
                ),
            ]
        )
        client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._request("GET", "/test")

        assert result == {"success": True}
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_connect_timeout(self):
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=[
                httpx.ConnectTimeout("Connect timed out"),
                httpx.ConnectTimeout("Connect timed out"),
                MagicMock(
                    raise_for_status=MagicMock(),
                    json=MagicMock(return_value={"success": True})
                ),
            ]
        )
        client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._request("GET", "/test")

        assert result == {"success": True}
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_none_after_max_retries_exceeded(self):
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client._request("GET", "/test")

        assert result is None
        assert mock_client.request.call_count == MAX_RETRIES
        assert mock_sleep.call_count == MAX_RETRIES - 1

    @pytest.mark.asyncio
    async def test_returns_none_on_http_status_error(self):
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.HTTPStatusError(
            "401 Unauthorized",
            response=mock_response,
            request=MagicMock()
        ))
        client._client = mock_client

        result = await client._request("GET", "/test")

        assert result is None
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_generic_exception(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=ValueError("Some error"))
        client._client = mock_client

        result = await client._request("GET", "/test")

        assert result is None
        mock_client.request.assert_called_once()


class TestApiClientMethods:
    """Tests for API client public methods (multi-agent API)."""

    @pytest.mark.asyncio
    async def test_register_machine_success(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "success": True,
            "data": {"id": "machine-uuid-123"}
        })
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.register_machine(agent_type="claude_code")

        assert result is True
        assert client.machine_uuids["claude_code"] == "machine-uuid-123"

    @pytest.mark.asyncio
    async def test_register_machine_failure(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result = await client.register_machine(agent_type="claude_code")

        assert result is False

    @pytest.mark.asyncio
    async def test_register_multiple_agents(self):
        """Register both claude_code and codex, verify both in machine_uuids."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "success": True,
            "data": {"id": "uuid-agent"}
        })
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        r1 = await client.register_machine(agent_type="claude_code")
        r2 = await client.register_machine(agent_type="codex")

        assert r1 is True
        assert r2 is True
        assert "claude_code" in client.machine_uuids
        assert "codex" in client.machine_uuids

    @pytest.mark.asyncio
    async def test_is_registered_returns_false_for_unknown(self):
        config = create_test_config()
        client = ApiClient(config)
        assert client.is_registered("nonexistent") is False

    @pytest.mark.asyncio
    async def test_is_registered_returns_true_after_register(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "success": True,
            "data": {"id": "uuid-123"}
        })
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        await client.register_machine(agent_type="claude_code")
        assert client.is_registered("claude_code") is True

    @pytest.mark.asyncio
    async def test_poll_tasks_returns_empty_when_not_registered(self):
        config = create_test_config()
        client = ApiClient(config)

        result = await client.poll_tasks("claude_code")

        assert result == []

    @pytest.mark.asyncio
    async def test_poll_tasks_returns_tasks_on_success(self):
        config = create_test_config()
        client = ApiClient(config)
        client.machine_uuids = {"claude_code": "test-machine-uuid"}

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "tasks": [
                {"task_id": "task-1", "instruction": "Do thing"},
                {"task_id": "task-2", "instruction": "Do other thing"},
            ]
        })
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.poll_tasks("claude_code")

        assert len(result) == 2
        assert result[0]["task_id"] == "task-1"

    @pytest.mark.asyncio
    async def test_poll_tasks_per_agent(self):
        """Each agent type polls its own machine UUID."""
        config = create_test_config()
        client = ApiClient(config)
        client.machine_uuids = {
            "claude_code": "uuid-claude",
            "codex": "uuid-codex",
        }

        mock_client = AsyncMock()

        def side_effect(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "uuid-claude" in url:
                resp.json = MagicMock(return_value={"tasks": [{"task_id": "claude-task"}]})
            else:
                resp.json = MagicMock(return_value={"tasks": [{"task_id": "codex-task"}]})
            return resp

        mock_client.request = AsyncMock(side_effect=side_effect)
        client._client = mock_client

        claude_tasks = await client.poll_tasks("claude_code")
        codex_tasks = await client.poll_tasks("codex")

        assert claude_tasks[0]["task_id"] == "claude-task"
        assert codex_tasks[0]["task_id"] == "codex-task"

    @pytest.mark.asyncio
    async def test_update_task_status_success(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.update_task_status("task-123", "running")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_task_status_failure(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result = await client.update_task_status("task-123", "running")

        assert result is False

    @pytest.mark.asyncio
    async def test_submit_result_success(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.submit_result("task-123", {"exit_code": 0, "stdout": "done", "stderr": ""})

        assert result is True

    @pytest.mark.asyncio
    async def test_submit_result_failure(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result = await client.submit_result("task-123", {"exit_code": 1, "stdout": "", "stderr": "error"})

        assert result is False

    @pytest.mark.asyncio
    async def test_submit_progress_success(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.submit_progress("task-123", "line1\n", "")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_reminder_success(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.send_reminder("task-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_reminder_failure(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result = await client.send_reminder("task-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_agent_status_returns_false_when_not_registered(self):
        config = create_test_config()
        client = ApiClient(config)

        result = await client.update_agent_status("claude_code", "busy")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_agent_status_success(self):
        config = create_test_config()
        client = ApiClient(config)
        client.machine_uuids = {"claude_code": "test-machine-uuid"}

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.update_agent_status("claude_code", "busy")

        assert result is True

    @pytest.mark.asyncio
    async def test_pin_task_session_success(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.pin_task_session("task-123", session_id="sess-abc", work_dir="/tmp/w")

        assert result is True
        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["json"]["session_id"] == "sess-abc"
        assert call_kwargs["json"]["work_dir"] == "/tmp/w"

    @pytest.mark.asyncio
    async def test_pin_task_session_failure(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result = await client.pin_task_session("task-123", session_id="sess-abc")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_task_returns_data(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True, "data": {"id": "task-123", "status": "running"}})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.get_task("task-123")

        assert result is not None
        assert result["id"] == "task-123"
        assert result["status"] == "running"


class TestApiClientClose:
    """Tests for API client cleanup."""

    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        client._client = mock_client

        await client.close()

        mock_client.aclose.assert_called_once()
