"""Integration tests for Cloud + Bridge end-to-end workflows.

Tests the complete chains:
- Chain A: Remote Execution (pending → dispatched → running → completed)
- Chain B: Windsurf Reminder (manual_only device + WeChat notification)
- Chain C: Timeout Handling (timeout error_type returned → task marked failed)
"""

import asyncio
import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Add cloud to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cloud"))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a test database engine with models registered."""
    # Import models to register them with Base.metadata
    from database import Base
    import models  # noqa: F401 - needed to register models

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """Create a test client with mocked database."""
    from database import get_db
    from main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


API_KEY = "test-api-key-12345"


def auth_headers():
    return {"X-API-Key": API_KEY}


# ─────────────────────────────────────────────────────────────────────────────
# Chain A: Remote Execution Integration Test
# Start cloud → Start Bridge → Create task → Observe pending → dispatched → running → completed
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chain_a_remote_execution_full_flow(client, db_session):
    """Test Chain A: Remote Execution full task lifecycle.

    Flow: Create task → Poll (dispatched) → Update status (running) → Submit result (completed)
    """
    # Step 1: Register a machine with remote_execution capability
    machine_payload = {
        "machine_id": "chain-a-machine",
        "machine_name": "Chain A Test Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    assert reg_response.status_code == 200
    machine_data = reg_response.json()["data"]
    machine_uuid = machine_data["id"]
    assert machine_data["status"] == "online"

    # Step 2: Create a task for this machine
    task_payload = {
        "instruction": "echo 'Hello from Chain A'",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    assert create_response.status_code == 200
    task_data = create_response.json()["data"]
    task_uuid = task_data["id"]
    assert task_data["status"] == "pending"
    assert task_data["instruction"] == "echo 'Hello from Chain A'"

    # Step 3: Poll tasks (simulates Bridge polling) - should return task and mark as dispatched
    poll_response = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())
    assert poll_response.status_code == 200
    poll_data = poll_response.json()
    assert "tasks" in poll_data
    assert len(poll_data["tasks"]) == 1
    assert poll_data["tasks"][0]["task_id"] == task_data["task_id"]
    assert poll_data["tasks"][0]["status"] == "dispatched"

    # Step 4: Bridge updates task status to running
    running_response = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "running"},
        headers=auth_headers(),
    )
    assert running_response.status_code == 200
    running_data = running_response.json()["data"]
    assert running_data["status"] == "running"
    assert running_data["started_at"] is not None

    # Step 5: Bridge submits result (simulates executor completing)
    result_payload = {
        "exit_code": 0,
        "stdout": "Hello from Chain A",
        "stderr": "",
    }
    result_response = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json=result_payload,
        headers=auth_headers(),
    )
    assert result_response.status_code == 200
    result_data = result_response.json()["data"]
    assert result_data["status"] == "completed"
    assert result_data["result"]["exit_code"] == 0
    assert result_data["result"]["stdout"] == "Hello from Chain A"
    assert result_data["completed_at"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Chain B: Windsurf Reminder Integration Test
# Create manual_only device → Create task → Start Bridge → Observe pending_manual status + WeChat message received
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chain_b_windsurf_reminder_flow(client, db_session):
    """Test Chain B: Windsurf Reminder flow with manual_only capability.

    Flow: Register manual_only machine → Create task → Trigger reminder → pending_manual + WeChat
    """
    # Step 1: Register a machine with manual_only capability
    machine_payload = {
        "machine_id": "windsurf-machine",
        "machine_name": "Windsurf Test Machine",
        "agent_type": "windsurf",
        "agent_capability": "manual_only",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    assert reg_response.status_code == 200
    machine_data = reg_response.json()["data"]
    machine_uuid = machine_data["id"]
    assert machine_data["agent_capability"] == "manual_only"

    # Step 2: Create a task for this manual_only machine
    task_payload = {
        "instruction": "Please open project and run tests",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    assert create_response.status_code == 200
    task_data = create_response.json()["data"]
    task_uuid = task_data["id"]
    assert task_data["status"] == "pending"

    # Step 3: Bridge sends reminder (simulates manual_only task handling)
    # Mock the WeChat notifier to avoid actual HTTP calls
    with patch("routers.tasks.send_wechat_markdown", new_callable=AsyncMock) as mock_wechat:
        mock_wechat.return_value = True
        remind_response = await client.post(
            f"/api/v1/tasks/{task_uuid}/remind",
            headers=auth_headers(),
        )
        assert remind_response.status_code == 200
        remind_data = remind_response.json()["data"]
        assert remind_data["status"] == "pending_manual"

        # Verify WeChat notification was called
        mock_wechat.assert_called_once()
        call_kwargs = mock_wechat.call_args.kwargs
        assert "⚠️ Windsurf 手动任务提醒" in call_kwargs["title"]  # title
        assert "Please open project and run tests" in call_kwargs["content"]  # content


@pytest.mark.asyncio
async def test_chain_b_reminder_updates_task_to_pending_manual(client, db_session):
    """Test that reminder correctly updates task status to pending_manual."""
    # Register manual_only machine
    machine_payload = {
        "machine_id": "windsurf-machine-2",
        "machine_name": "Windsurf Machine 2",
        "agent_type": "windsurf",
        "agent_capability": "manual_only",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Create task
    task_payload = {
        "instruction": "Manual task",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_uuid = create_response.json()["data"]["id"]

    # Verify initial status is pending
    get_response = await client.get(f"/api/v1/tasks/{task_uuid}", headers=auth_headers())
    assert get_response.json()["data"]["status"] == "pending"

    # Trigger reminder
    with patch("routers.tasks.send_wechat_markdown", new_callable=AsyncMock) as mock_wechat:
        mock_wechat.return_value = True
        await client.post(f"/api/v1/tasks/{task_uuid}/remind", headers=auth_headers())

    # Verify status changed to pending_manual
    get_response = await client.get(f"/api/v1/tasks/{task_uuid}", headers=auth_headers())
    assert get_response.json()["data"]["status"] == "pending_manual"


# ─────────────────────────────────────────────────────────────────────────────
# Chain C: Timeout Handling Integration Test
# Create task with timeout_seconds=10 → Execute sleep 30 → Observe timeout error_type returned → Task marked failed
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chain_c_timeout_handling_flow(client, db_session):
    """Test Chain C: Timeout error handling.

    Flow: Create task with timeout → Execute (times out) → Submit result with error_type=timeout → Task marked failed
    """
    # Step 1: Register a machine
    machine_payload = {
        "machine_id": "timeout-machine",
        "machine_name": "Timeout Test Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Step 2: Create a task with short timeout
    task_payload = {
        "instruction": "sleep 30",  # Long-running command
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_data = create_response.json()["data"]
    task_uuid = task_data["id"]

    # Step 3: Poll to dispatch task
    poll_response = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())
    assert poll_response.json()["tasks"][0]["task_id"] == task_data["task_id"]

    # Step 4: Bridge updates status to running
    await client.put(f"/api/v1/tasks/{task_uuid}", json={"status": "running"}, headers=auth_headers())

    # Step 5: Executor times out (simulated) and Bridge submits timeout result
    timeout_result = {
        "exit_code": -1,
        "stdout": "",
        "stderr": "Command timed out after 10 seconds",
        "error_type": "timeout",
    }
    result_response = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json=timeout_result,
        headers=auth_headers(),
    )
    assert result_response.status_code == 200
    result_data = result_response.json()["data"]
    assert result_data["status"] == "failed"
    assert result_data["result"]["error_type"] == "timeout"
    assert result_data["error_message"] == "Command timed out after 10 seconds"
    assert result_data["completed_at"] is not None


@pytest.mark.asyncio
async def test_chain_c_timeout_error_type_in_result(client, db_session):
    """Test that timeout error_type is properly stored in task result."""
    # Register machine
    machine_payload = {
        "machine_id": "timeout-machine-2",
        "machine_name": "Timeout Test Machine 2",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Create task
    task_payload = {
        "instruction": "long-running-command",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_uuid = create_response.json()["data"]["id"]

    # Poll and update to running
    await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())
    await client.put(f"/api/v1/tasks/{task_uuid}", json={"status": "running"}, headers=auth_headers())

    # Submit timeout result
    timeout_result = {
        "exit_code": -1,
        "stdout": "",
        "stderr": "",
        "error_type": "timeout",
    }
    result_response = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json=timeout_result,
        headers=auth_headers(),
    )
    result_data = result_response.json()["data"]

    # Verify error_type is preserved
    assert result_data["result"]["error_type"] == "timeout"
    assert result_data["status"] == "failed"


# ─────────────────────────────────────────────────────────────────────────────
# Additional Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_status_transition_validation(client, db_session):
    """Test that invalid status transitions are rejected."""
    # Register machine and create task
    machine_payload = {
        "machine_id": "transition-test-machine",
        "machine_name": "Transition Test Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    task_payload = {
        "instruction": "test command",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_uuid = create_response.json()["data"]["id"]

    # Cannot go from pending directly to completed (must go through dispatched/running)
    invalid_response = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "completed"},
        headers=auth_headers(),
    )
    assert invalid_response.status_code == 400

    # Cannot go from pending to running directly (must dispatch first)
    invalid_response2 = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "running"},
        headers=auth_headers(),
    )
    assert invalid_response2.status_code == 400


@pytest.mark.asyncio
async def test_multiple_tasks_same_machine(client, db_session):
    """Test handling multiple tasks for the same machine."""
    # Register machine
    machine_payload = {
        "machine_id": "multi-task-machine",
        "machine_name": "Multi Task Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Create multiple tasks
    task_ids = []
    for i in range(3):
        task_payload = {
            "instruction": f"task {i}",
            "target_machine_id": machine_uuid,
        }
        create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
        task_ids.append(create_response.json()["data"]["id"])

    # Poll should return all pending tasks
    poll_response = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())
    poll_data = poll_response.json()
    assert len(poll_data["tasks"]) == 3

    # All tasks should be marked as dispatched
    for task_id in task_ids:
        get_response = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers())
        assert get_response.json()["data"]["status"] == "dispatched"


@pytest.mark.asyncio
async def test_machine_dashboard_shows_running_tasks(client, db_session):
    """Test that machine dashboard correctly shows running tasks."""
    # Register machine
    machine_payload = {
        "machine_id": "dashboard-test-machine",
        "machine_name": "Dashboard Test Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Create and start a task
    task_payload = {
        "instruction": "running task",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_uuid = create_response.json()["data"]["id"]

    # Dispatch and run
    await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())
    await client.put(f"/api/v1/tasks/{task_uuid}", json={"status": "running"}, headers=auth_headers())

    # Check dashboard
    dashboard_response = await client.get("/api/v1/machines/dashboard", headers=auth_headers())
    dashboard_data = dashboard_response.json()["data"]
    assert len(dashboard_data) >= 1

    machine_dashboard = next((m for m in dashboard_data if m["machine_id"] == "dashboard-test-machine"), None)
    assert machine_dashboard is not None
    assert len(machine_dashboard["running_tasks"]) == 1
    assert machine_dashboard["running_tasks"][0]["task_id"] == create_response.json()["data"]["task_id"]


@pytest.mark.asyncio
async def test_callback_endpoint_functions_same_as_result(client, db_session):
    """Test that callback endpoint works the same as result endpoint."""
    # Register machine
    machine_payload = {
        "machine_id": "callback-test-machine",
        "machine_name": "Callback Test Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Create task
    task_payload = {
        "instruction": "callback test",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_uuid = create_response.json()["data"]["id"]

    # Dispatch
    await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())

    # Submit via callback
    callback_payload = {
        "exit_code": 0,
        "stdout": "Callback output",
        "stderr": "",
    }
    callback_response = await client.post(
        f"/api/v1/tasks/{task_uuid}/callback",
        json=callback_payload,
        headers=auth_headers(),
    )
    assert callback_response.status_code == 200
    callback_data = callback_response.json()["data"]
    assert callback_data["status"] == "completed"
    assert callback_data["result"]["stdout"] == "Callback output"


@pytest.mark.asyncio
async def test_cancel_pending_task(client, db_session):
    """Test cancelling a pending task."""
    # Register machine
    machine_payload = {
        "machine_id": "cancel-test-machine",
        "machine_name": "Cancel Test Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Create task
    task_payload = {
        "instruction": "cancellable task",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_uuid = create_response.json()["data"]["id"]

    # Cancel pending task
    cancel_response = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "cancelled"},
        headers=auth_headers(),
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_dispatched_task(client, db_session):
    """Test cancelling a dispatched task."""
    # Register machine
    machine_payload = {
        "machine_id": "cancel-dispatched-machine",
        "machine_name": "Cancel Dispatched Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    reg_response = await client.post("/api/v1/machines", json=machine_payload, headers=auth_headers())
    machine_uuid = reg_response.json()["data"]["id"]

    # Create and dispatch task
    task_payload = {
        "instruction": "dispatched task",
        "target_machine_id": machine_uuid,
    }
    create_response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    task_uuid = create_response.json()["data"]["id"]
    await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())

    # Verify dispatched
    get_response = await client.get(f"/api/v1/tasks/{task_uuid}", headers=auth_headers())
    assert get_response.json()["data"]["status"] == "dispatched"

    # Cancel dispatched task
    cancel_response = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "cancelled"},
        headers=auth_headers(),
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"
