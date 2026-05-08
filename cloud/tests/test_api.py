"""Tests for Cloud API endpoints using httpx.AsyncClient + pytest-asyncio."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app
from database import get_db


API_KEY = "test-api-key-12345"


def auth_headers():
    return {"X-API-Key": API_KEY}


# ─────────────────────────────────────────────────────────────────────────────
# Machine API Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_machine(client, db_session):
    """Test POST /api/v1/machines - register a new machine."""
    payload = {
        "machine_id": "test-machine-001",
        "machine_name": "Test Machine",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
    }
    response = await client.post("/api/v1/machines", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["machine_id"] == "test-machine-001"
    assert data["data"]["status"] == "online"


@pytest.mark.asyncio
async def test_register_machine_auto_create_project(client, db_session):
    """Test POST /api/v1/machines - auto-creates project if not exists."""
    payload = {
        "machine_id": "test-machine-002",
        "machine_name": "Test Machine 2",
        "agent_type": "claude_code",
        "agent_capability": "remote_execution",
        "project_id": "auto-project-001",
    }
    response = await client.post("/api/v1/machines", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_list_machines(client, db_session):
    """Test GET /api/v1/machines - list all machines."""
    # First register a machine
    await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "list-test-machine",
            "machine_name": "List Test Machine",
            "agent_type": "claude_code",
            "agent_capability": "remote_execution",
        },
        headers=auth_headers(),
    )
    response = await client.get("/api/v1/machines", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_get_machine_dashboard(client, db_session):
    """Test GET /api/v1/machines/dashboard - get all machines with running tasks."""
    # Register a machine first
    await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "dashboard-test-machine",
            "machine_name": "Dashboard Test Machine",
            "agent_type": "claude_code",
            "agent_capability": "remote_execution",
        },
        headers=auth_headers(),
    )
    response = await client.get("/api/v1/machines/dashboard", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_get_machine_details(client, db_session):
    """Test GET /api/v1/machines/{uuid} - get machine details."""
    # Register a machine first
    reg_response = await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "detail-test-machine",
            "machine_name": "Detail Test Machine",
            "agent_type": "claude_code",
            "agent_capability": "remote_execution",
        },
        headers=auth_headers(),
    )
    machine_uuid = reg_response.json()["data"]["id"]

    response = await client.get(f"/api/v1/machines/{machine_uuid}", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["machine_id"] == "detail-test-machine"
    assert "pending_task_count" in data["data"]


@pytest.mark.asyncio
async def test_update_machine_status(client, db_session):
    """Test PATCH /api/v1/machines/{uuid} - update machine status."""
    # Register a machine first
    reg_response = await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "update-test-machine",
            "machine_name": "Update Test Machine",
            "agent_type": "claude_code",
            "agent_capability": "remote_execution",
        },
        headers=auth_headers(),
    )
    machine_uuid = reg_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/machines/{machine_uuid}",
        json={"is_enabled": False},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["is_enabled"] is False


@pytest.mark.asyncio
async def test_poll_tasks(client, db_session):
    """Test GET /api/v1/machines/{uuid}/poll - poll for pending tasks."""
    # Register a machine first
    reg_response = await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "poll-test-machine",
            "machine_name": "Poll Test Machine",
            "agent_type": "claude_code",
            "agent_capability": "remote_execution",
        },
        headers=auth_headers(),
    )
    machine_uuid = reg_response.json()["data"]["id"]

    # Poll should return empty list initially
    response = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert "machine" in data
    assert "tasks" in data
    assert isinstance(data["tasks"], list)


# ─────────────────────────────────────────────────────────────────────────────
# Task API Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_task(client, db_session):
    """Test POST /api/v1/tasks - create a new task."""
    payload = {
        "instruction": "Test task instruction",
    }
    response = await client.post("/api/v1/tasks", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["instruction"] == "Test task instruction"
    assert data["data"]["status"] == "pending"
    assert "task_id" in data["data"]
    assert data["data"]["task_id"].startswith("task-")


@pytest.mark.asyncio
async def test_create_task_with_target_machine(client, db_session):
    """Test POST /api/v1/tasks - create a task with target machine."""
    # Register a machine first
    reg_response = await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "target-machine-001",
            "machine_name": "Target Machine",
            "agent_type": "claude_code",
            "agent_capability": "remote_execution",
        },
        headers=auth_headers(),
    )
    machine_uuid = reg_response.json()["data"]["id"]

    # Create task with target machine
    payload = {
        "instruction": "Task for specific machine",
        "target_machine_id": machine_uuid,
    }
    response = await client.post("/api/v1/tasks", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["target_machine_id"] == machine_uuid


@pytest.mark.asyncio
async def test_list_tasks(client, db_session):
    """Test GET /api/v1/tasks - list tasks with pagination."""
    # Create a task first
    await client.post(
        "/api/v1/tasks",
        json={"instruction": "List test task"},
        headers=auth_headers(),
    )
    response = await client.get("/api/v1/tasks", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_list_tasks_with_status_filter(client, db_session):
    """Test GET /api/v1/tasks - filter by status."""
    # Create a pending task
    await client.post(
        "/api/v1/tasks",
        json={"instruction": "Pending task"},
        headers=auth_headers(),
    )
    response = await client.get("/api/v1/tasks?status=pending", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    for task in data["data"]:
        assert task["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task_details(client, db_session):
    """Test GET /api/v1/tasks/{uuid} - get task details."""
    # Create a task first
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Detail test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    response = await client.get(f"/api/v1/tasks/{task_uuid}", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["instruction"] == "Detail test task"
    assert "result" in data["data"]


@pytest.mark.asyncio
async def test_update_task_status(client, db_session):
    """Test PUT /api/v1/tasks/{uuid} - update task status."""
    # Create a task first
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Update status test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    # Update status to dispatched
    response = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "dispatched"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "dispatched"


@pytest.mark.asyncio
async def test_update_task_status_invalid_transition(client, db_session):
    """Test PUT /api/v1/tasks/{uuid} - invalid status transition."""
    # Create a task first
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Invalid transition test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    # Try invalid transition: pending -> completed (should fail, need dispatched first)
    response = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "completed"},
        headers=auth_headers(),
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_task_result(client, db_session):
    """Test POST /api/v1/tasks/{uuid}/result - submit execution result."""
    # Create a task first
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Result test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    # Submit result
    payload = {
        "exit_code": 0,
        "stdout": "Task completed successfully",
        "stderr": "",
    }
    response = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_submit_task_result_with_error(client, db_session):
    """Test POST /api/v1/tasks/{uuid}/result - submit result with error."""
    # Create a task first
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Error result test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    # Submit error result
    payload = {
        "exit_code": 1,
        "stdout": "",
        "stderr": "Something went wrong",
        "error_type": "execution_error",
    }
    response = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "failed"


@pytest.mark.asyncio
async def test_task_callback(client, db_session):
    """Test POST /api/v1/tasks/{uuid}/callback - task callback."""
    # Create a task first
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Callback test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    # Submit callback
    payload = {
        "exit_code": 0,
        "stdout": "Callback completed",
        "stderr": "",
    }
    response = await client.post(
        f"/api/v1/tasks/{task_uuid}/callback",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_trigger_reminder(client, db_session):
    """Test POST /api/v1/tasks/{uuid}/remind - trigger reminder."""
    # Register a machine and create a task with it
    reg_response = await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "remind-test-machine",
            "machine_name": "Remind Test Machine",
            "agent_type": "claude_code",
            "agent_capability": "manual_only",
        },
        headers=auth_headers(),
    )
    machine_uuid = reg_response.json()["data"]["id"]

    create_response = await client.post(
        "/api/v1/tasks",
        json={
            "instruction": "Manual task that needs reminder",
            "target_machine_id": machine_uuid,
        },
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    # Trigger reminder (WeChat notification is mocked in notifier)
    response = await client.post(
        f"/api/v1/tasks/{task_uuid}/remind",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "pending_manual"


# ─────────────────────────────────────────────────────────────────────────────
# Project API Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_project(client, db_session):
    """Test POST /api/v1/projects - create a new project."""
    payload = {
        "project_name": "Test Project",
        "root_path": "/tmp/test",
        "idle_threshold_hours": 48,
        "reminder_interval_hours": 24,
    }
    response = await client.post("/api/v1/projects", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["project_name"] == "Test Project"
    assert data["data"]["idle_threshold_hours"] == 48


@pytest.mark.asyncio
async def test_list_projects(client, db_session):
    """Test GET /api/v1/projects - list all projects."""
    # Create a project first
    await client.post(
        "/api/v1/projects",
        json={"project_name": "List Test Project"},
        headers=auth_headers(),
    )
    response = await client.get("/api/v1/projects", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_update_project(client, db_session):
    """Test PUT /api/v1/projects/{uuid} - update project."""
    # Create a project first
    create_response = await client.post(
        "/api/v1/projects",
        json={
            "project_name": "Update Test Project",
            "idle_threshold_hours": 24,
        },
        headers=auth_headers(),
    )
    project_uuid = create_response.json()["data"]["id"]

    # Update project
    response = await client.put(
        f"/api/v1/projects/{project_uuid}",
        json={"idle_threshold_hours": 72},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["idle_threshold_hours"] == 72


@pytest.mark.asyncio
async def test_update_project_archive(client, db_session):
    """Test PUT /api/v1/projects/{uuid} - archive project."""
    # Create a project first
    create_response = await client.post(
        "/api/v1/projects",
        json={"project_name": "Archive Test Project"},
        headers=auth_headers(),
    )
    project_uuid = create_response.json()["data"]["id"]

    # Archive project
    response = await client.put(
        f"/api/v1/projects/{project_uuid}",
        json={"is_archived": True},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["is_archived"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Authentication Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_endpoint_no_auth(client):
    """Test /health endpoint does not require authentication."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_without_key_fails(client, db_session):
    """Test API requests without API key fail."""
    response = await client.get("/api/v1/machines")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_with_short_key_fails(client, db_session):
    """Test API requests with too-short API key fail."""
    response = await client.get("/api/v1/machines", headers={"X-API-Key": "short"})
    assert response.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Issue API Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_issue(client, db_session):
    """Test POST /api/v1/issues - create a new issue."""
    payload = {
        "title": "Test Issue",
        "description": "Issue description",
        "status": "todo",
        "priority": "high",
    }
    response = await client.post("/api/v1/issues", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["title"] == "Test Issue"
    assert data["data"]["status"] == "todo"
    assert data["data"]["priority"] == "high"
    assert data["data"]["issue_id"].startswith("issue-")


@pytest.mark.asyncio
async def test_create_issue_auto_dispatch_task(client, db_session):
    """Test POST /api/v1/issues - auto-dispatches task when assigned to machine."""
    # Register a machine first
    reg_response = await client.post(
        "/api/v1/machines",
        json={
            "machine_id": "issue-machine-001",
            "machine_name": "Issue Test Machine",
            "agent_type": "claude_code",
            "agent_capability": "remote_execution",
        },
        headers=auth_headers(),
    )
    machine_uuid = reg_response.json()["data"]["id"]

    payload = {
        "title": "Auto-dispatch Issue",
        "description": "Please fix the bug",
        "status": "todo",
        "priority": "medium",
        "assignee_type": "machine",
        "assignee_id": machine_uuid,
    }
    response = await client.post("/api/v1/issues", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify a task was auto-created
    issue_uuid = data["data"]["id"]
    tasks_response = await client.get(f"/api/v1/issues/{issue_uuid}/tasks", headers=auth_headers())
    tasks_data = tasks_response.json()["data"]
    assert len(tasks_data) == 1
    assert tasks_data[0]["status"] == "pending"
    assert tasks_data[0]["target_machine_id"] == machine_uuid


@pytest.mark.asyncio
async def test_list_issues(client, db_session):
    """Test GET /api/v1/issues - list issues."""
    await client.post(
        "/api/v1/issues",
        json={"title": "Issue 1", "status": "todo", "priority": "low"},
        headers=auth_headers(),
    )
    await client.post(
        "/api/v1/issues",
        json={"title": "Issue 2", "status": "in_progress", "priority": "high"},
        headers=auth_headers(),
    )
    response = await client.get("/api/v1/issues", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 2
    assert "meta" in data
    assert "total" in data["meta"]


@pytest.mark.asyncio
async def test_list_issues_with_status_filter(client, db_session):
    """Test GET /api/v1/issues - filter by status."""
    await client.post(
        "/api/v1/issues",
        json={"title": "Todo Issue", "status": "todo", "priority": "low"},
        headers=auth_headers(),
    )
    response = await client.get("/api/v1/issues?status=todo", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    for issue in data["data"]:
        assert issue["status"] == "todo"


@pytest.mark.asyncio
async def test_get_issue_details(client, db_session):
    """Test GET /api/v1/issues/{uuid} - get issue details with tasks."""
    create_response = await client.post(
        "/api/v1/issues",
        json={"title": "Detail Issue", "status": "todo", "priority": "medium"},
        headers=auth_headers(),
    )
    issue_uuid = create_response.json()["data"]["id"]

    response = await client.get(f"/api/v1/issues/{issue_uuid}", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["title"] == "Detail Issue"
    assert "tasks" in data["data"]


@pytest.mark.asyncio
async def test_update_issue(client, db_session):
    """Test PUT /api/v1/issues/{uuid} - update issue."""
    create_response = await client.post(
        "/api/v1/issues",
        json={"title": "Original Title", "status": "todo", "priority": "low"},
        headers=auth_headers(),
    )
    issue_uuid = create_response.json()["data"]["id"]

    response = await client.put(
        f"/api/v1/issues/{issue_uuid}",
        json={"title": "Updated Title", "priority": "urgent"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["title"] == "Updated Title"
    assert data["data"]["priority"] == "urgent"


@pytest.mark.asyncio
async def test_update_issue_reconcile_tasks(client, db_session):
    """Test PUT /api/v1/issues - reassigning cancels old task and creates new."""
    # Register two machines
    reg1 = await client.post(
        "/api/v1/machines",
        json={"machine_id": "m1", "machine_name": "M1", "agent_type": "claude_code", "agent_capability": "remote_execution"},
        headers=auth_headers(),
    )
    m1_uuid = reg1.json()["data"]["id"]
    reg2 = await client.post(
        "/api/v1/machines",
        json={"machine_id": "m2", "machine_name": "M2", "agent_type": "claude_code", "agent_capability": "remote_execution"},
        headers=auth_headers(),
    )
    m2_uuid = reg2.json()["data"]["id"]

    # Create issue assigned to m1
    create_response = await client.post(
        "/api/v1/issues",
        json={
            "title": "Reconcile Test",
            "status": "todo",
            "priority": "medium",
            "assignee_type": "machine",
            "assignee_id": m1_uuid,
        },
        headers=auth_headers(),
    )
    issue_uuid = create_response.json()["data"]["id"]

    # Reassign to m2
    await client.put(
        f"/api/v1/issues/{issue_uuid}",
        json={"assignee_id": m2_uuid},
        headers=auth_headers(),
    )

    # Verify old task cancelled and new task created
    tasks_response = await client.get(f"/api/v1/issues/{issue_uuid}/tasks", headers=auth_headers())
    tasks = tasks_response.json()["data"]
    assert len(tasks) == 2
    statuses = [t["status"] for t in tasks]
    assert "cancelled" in statuses
    assert "pending" in statuses


@pytest.mark.asyncio
async def test_delete_issue_cancels_tasks(client, db_session):
    """Test DELETE /api/v1/issues - cascades cancellation to tasks."""
    reg = await client.post(
        "/api/v1/machines",
        json={"machine_id": "del-m", "machine_name": "Del M", "agent_type": "claude_code", "agent_capability": "remote_execution"},
        headers=auth_headers(),
    )
    m_uuid = reg.json()["data"]["id"]

    create_response = await client.post(
        "/api/v1/issues",
        json={
            "title": "Delete Test",
            "status": "todo",
            "assignee_type": "machine",
            "assignee_id": m_uuid,
        },
        headers=auth_headers(),
    )
    issue_uuid = create_response.json()["data"]["id"]

    # Delete issue
    response = await client.delete(f"/api/v1/issues/{issue_uuid}", headers=auth_headers())
    assert response.status_code == 200

    # Verify tasks are cancelled
    tasks_response = await client.get(f"/api/v1/issues/{issue_uuid}/tasks", headers=auth_headers())
    tasks = tasks_response.json()["data"]
    for t in tasks:
        assert t["status"] == "cancelled"


@pytest.mark.asyncio
async def test_create_task_with_issue_id(client, db_session):
    """Test POST /api/v1/tasks - create task linked to an issue."""
    issue_response = await client.post(
        "/api/v1/issues",
        json={"title": "Linked Issue", "status": "todo", "priority": "medium"},
        headers=auth_headers(),
    )
    issue_uuid = issue_response.json()["data"]["id"]

    task_payload = {
        "instruction": "Task for issue",
        "issue_id": issue_uuid,
    }
    response = await client.post("/api/v1/tasks", json=task_payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["issue_id"] == issue_uuid


@pytest.mark.asyncio
async def test_submit_result_with_session_and_workdir(client, db_session):
    """Test POST /api/v1/tasks/{uuid}/result - saves session_id and work_dir."""
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Session test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    result_payload = {
        "exit_code": 0,
        "stdout": "done",
        "stderr": "",
        "session_id": "sess-abc123",
        "work_dir": "/tmp/work/123",
    }
    response = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json=result_payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["session_id"] == "sess-abc123"
    assert data["work_dir"] == "/tmp/work/123"


@pytest.mark.asyncio
async def test_pin_task_session(client, db_session):
    """Test PUT /api/v1/tasks/{uuid}/pin - mid-run session pinning."""
    create_response = await client.post(
        "/api/v1/tasks",
        json={"instruction": "Pin test task"},
        headers=auth_headers(),
    )
    task_uuid = create_response.json()["data"]["id"]

    response = await client.put(
        f"/api/v1/tasks/{task_uuid}/pin",
        json={"session_id": "sess-midrun", "work_dir": "/tmp/mid"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["session_id"] == "sess-midrun"
    assert data["work_dir"] == "/tmp/mid"
