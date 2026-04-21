"""Tests for bridge API client retry logic using mocked HTTP responses."""

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
            agent_type="claude_code",
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
        """Test successful request returns parsed JSON data."""
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
        """Test retry logic triggers on ConnectError."""
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        # First two calls fail with ConnectError, third succeeds
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
        assert mock_sleep.call_count == 2  # Sleep between retries

    @pytest.mark.asyncio
    async def test_retry_on_read_timeout(self):
        """Test retry logic triggers on ReadTimeout."""
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        # First two calls fail with ReadTimeout, third succeeds
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

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client._request("GET", "/test")

        assert result == {"success": True}
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_connect_timeout(self):
        """Test retry logic triggers on ConnectTimeout."""
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        # First two calls fail with ConnectTimeout, third succeeds
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

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client._request("GET", "/test")

        assert result == {"success": True}
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_none_after_max_retries_exceeded(self):
        """Test returns None when all retries are exhausted."""
        config = create_test_config()
        client = ApiClient(config)

        import httpx

        mock_client = AsyncMock()
        # All calls fail with ConnectError
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client._request("GET", "/test")

        assert result is None
        assert mock_client.request.call_count == MAX_RETRIES
        assert mock_sleep.call_count == MAX_RETRIES - 1

    @pytest.mark.asyncio
    async def test_returns_none_on_http_status_error(self):
        """Test returns None immediately on HTTPStatusError (no retry)."""
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
        mock_client.request.assert_called_once()  # No retries for HTTP errors

    @pytest.mark.asyncio
    async def test_returns_none_on_generic_exception(self):
        """Test returns None immediately on generic exception (no retry)."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=ValueError("Some error"))
        client._client = mock_client

        result = await client._request("GET", "/test")

        assert result is None
        mock_client.request.assert_called_once()  # No retries for generic errors


class TestApiClientMethods:
    """Tests for API client public methods."""

    @pytest.mark.asyncio
    async def test_register_machine_success(self):
        """Test register_machine returns True on success."""
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

        result = await client.register_machine()

        assert result is True
        assert client.machine_uuid == "machine-uuid-123"

    @pytest.mark.asyncio
    async def test_register_machine_failure(self):
        """Test register_machine returns False on failure."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)  # Simulates all retries failed
        client._client = mock_client

        result = await client.register_machine()

        assert result is False

    @pytest.mark.asyncio
    async def test_poll_tasks_returns_empty_when_not_registered(self):
        """Test poll_tasks returns empty list when machine not registered."""
        config = create_test_config()
        client = ApiClient(config)
        client.machine_uuid = None

        result = await client.poll_tasks()

        assert result == []

    @pytest.mark.asyncio
    async def test_poll_tasks_returns_tasks_on_success(self):
        """Test poll_tasks returns list of tasks on success."""
        config = create_test_config()
        client = ApiClient(config)
        client.machine_uuid = "test-machine-uuid"

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

        result = await client.poll_tasks()

        assert len(result) == 2
        assert result[0]["task_id"] == "task-1"

    @pytest.mark.asyncio
    async def test_update_task_status_success(self):
        """Test update_task_status returns True on success."""
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
        """Test update_task_status returns False on failure."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result = await client.update_task_status("task-123", "running")

        assert result is False

    @pytest.mark.asyncio
    async def test_submit_result_success(self):
        """Test submit_result returns True on success."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result_data = {"exit_code": 0, "stdout": "done", "stderr": ""}
        result = await client.submit_result("task-123", result_data)

        assert result is True

    @pytest.mark.asyncio
    async def test_submit_result_failure(self):
        """Test submit_result returns False on failure."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result_data = {"exit_code": 1, "stdout": "", "stderr": "error"}
        result = await client.submit_result("task-123", result_data)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_reminder_success(self):
        """Test send_reminder returns True on success."""
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
        """Test send_reminder returns False on failure."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=None)
        client._client = mock_client

        result = await client.send_reminder("task-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_agent_status_returns_false_when_not_registered(self):
        """Test update_agent_status returns False when machine not registered."""
        config = create_test_config()
        client = ApiClient(config)
        client.machine_uuid = None

        result = await client.update_agent_status("busy")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_agent_status_success(self):
        """Test update_agent_status returns True on success."""
        config = create_test_config()
        client = ApiClient(config)
        client.machine_uuid = "test-machine-uuid"

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True})
        mock_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.update_agent_status("busy")

        assert result is True


class TestApiClientClose:
    """Tests for API client cleanup."""

    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        """Test close calls aclose on the HTTP client."""
        config = create_test_config()
        client = ApiClient(config)

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        client._client = mock_client

        await client.close()

        mock_client.aclose.assert_called_once()
