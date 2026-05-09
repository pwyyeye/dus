"""End-to-end flow tests covering the complete task lifecycle.

Tests the full chain from issue creation through task execution:
1. Machine registration
2. Issue creation with assignee (auto-dispatches task)
3. Bridge polling (task dispatched)
4. Agent execution (task running)
5. Result submission (task completed)
"""

import asyncio
import uuid
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cloud"))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    from database import Base
    import models  # noqa: F401

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    from database import get_db
    from main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


API_KEY = "test-api-key-12345"


def auth():
    return {"X-API-Key": API_KEY}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: register a machine and return its UUID
# ─────────────────────────────────────────────────────────────────────────────


async def register_machine(client, machine_id="e2e-machine", capability="remote_execution"):
    resp = await client.post(
        "/api/v1/machines",
        json={
            "machine_id": machine_id,
            "machine_name": f"{machine_id} name",
            "agent_type": "claude_code",
            "agent_capability": capability,
        },
        headers=auth(),
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Issue -> auto-dispatch -> poll -> run -> complete
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_issue_to_task_completion(client, db_session):
    """Full flow: create issue -> auto-dispatched task -> poll -> run -> complete."""
    machine_uuid = await register_machine(client)

    # Create issue assigned to machine
    issue_resp = await client.post(
        "/api/v1/issues",
        json={
            "title": "Fix login bug",
            "description": "Users cannot log in",
            "status": "todo",
            "priority": "high",
            "assignee_type": "machine",
            "assignee_id": machine_uuid,
        },
        headers=auth(),
    )
    assert issue_resp.status_code == 200
    issue_data = issue_resp.json()["data"]
    issue_uuid = issue_data["id"]
    assert issue_data["status"] == "todo"
    assert issue_data["issue_id"].startswith("issue-")

    # Bridge polls - should get the auto-dispatched task
    poll_resp = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth())
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()
    assert len(poll_data["tasks"]) == 1
    task = poll_data["tasks"][0]
    task_uuid = task["id"]
    assert task["status"] == "dispatched"
    assert task["issue_id"] == issue_uuid
    assert task["instruction"] == "Fix login bug\n\nUsers cannot log in"

    # Bridge updates task to running
    run_resp = await client.put(
        f"/api/v1/tasks/{task_uuid}",
        json={"status": "running"},
        headers=auth(),
    )
    assert run_resp.status_code == 200
    assert run_resp.json()["data"]["status"] == "running"
    assert run_resp.json()["data"]["started_at"] is not None

    # Agent completes - bridge submits result
    result_resp = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json={"exit_code": 0, "stdout": "Fixed!", "stderr": ""},
        headers=auth(),
    )
    assert result_resp.status_code == 200
    result_data = result_resp.json()["data"]
    assert result_data["status"] == "completed"
    assert result_data["result"]["exit_code"] == 0
    assert result_data["result"]["stdout"] == "Fixed!"
    assert result_data["completed_at"] is not None

    # Verify via GET
    get_resp = await client.get(f"/api/v1/tasks/{task_uuid}", headers=auth())
    assert get_resp.json()["data"]["status"] == "completed"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Issue with agent assignee -> agent_config in poll
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_issue_with_agent_assignee(client, db_session):
    """Issue assigned to agent -> task dispatched to agent's machine with agent_config."""
    machine_uuid = await register_machine(client)

    # Create an agent on the machine
    agent_resp = await client.post(
        "/api/v1/agents",
        json={
            "name": "code-reviewer",
            "description": "Reviews code",
            "machine_id": machine_uuid,
            "instructions": "Review the code for bugs",
            "model": "claude-sonnet-4-20250514",
        },
        headers=auth(),
    )
    assert agent_resp.status_code == 200
    agent_uuid = agent_resp.json()["data"]["id"]

    # Create issue assigned to agent
    issue_resp = await client.post(
        "/api/v1/issues",
        json={
            "title": "Review PR #42",
            "status": "todo",
            "assignee_type": "agent",
            "assignee_id": agent_uuid,
        },
        headers=auth(),
    )
    assert issue_resp.status_code == 200
    issue_uuid = issue_resp.json()["data"]["id"]

    # Poll - task should be dispatched to the agent's machine
    poll_resp = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth())
    assert poll_resp.status_code == 200
    tasks = poll_resp.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["issue_id"] == issue_uuid

    # Agent config should be included in the task's poll response
    agent_config = tasks[0].get("agent_config")
    assert agent_config is not None
    assert agent_config["instructions"] == "Review the code for bugs"
    assert agent_config["model"] == "claude-sonnet-4-20250514"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Task failure
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_task_failure(client, db_session):
    """Task execution fails -> status becomes 'failed' with error info."""
    machine_uuid = await register_machine(client, "fail-machine")

    # Create issue
    issue_resp = await client.post(
        "/api/v1/issues",
        json={
            "title": "Risky change",
            "status": "todo",
            "assignee_type": "machine",
            "assignee_id": machine_uuid,
        },
        headers=auth(),
    )
    issue_uuid = issue_resp.json()["data"]["id"]

    # Poll -> dispatch
    poll_resp = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth())
    task_uuid = poll_resp.json()["tasks"][0]["id"]

    # Run
    await client.put(f"/api/v1/tasks/{task_uuid}", json={"status": "running"}, headers=auth())

    # Submit failure
    fail_resp = await client.post(
        f"/api/v1/tasks/{task_uuid}/result",
        json={
            "exit_code": 1,
            "stdout": "",
            "stderr": "SyntaxError on line 42",
            "error_type": "execution_error",
        },
        headers=auth(),
    )
    assert fail_resp.status_code == 200
    assert fail_resp.json()["data"]["status"] == "failed"
    assert fail_resp.json()["data"]["error_message"] == "SyntaxError on line 42"

    # Verify task appears in issue's task list
    tasks_resp = await client.get(f"/api/v1/issues/{issue_uuid}/tasks", headers=auth())
    assert len(tasks_resp.json()["data"]) == 1
    assert tasks_resp.json()["data"][0]["status"] == "failed"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Session resumption across issue tasks
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_session_resumption(client, db_session):
    """Completed task stores session_id/work_dir; next task for same issue gets them as prior."""
    machine_uuid = await register_machine(client, "resume-machine")

    # Create issue
    issue_resp = await client.post(
        "/api/v1/issues",
        json={
            "title": "Multi-step task",
            "status": "todo",
            "assignee_type": "machine",
            "assignee_id": machine_uuid,
        },
        headers=auth(),
    )
    issue_uuid = issue_resp.json()["data"]["id"]

    # First cycle: poll -> run -> complete with session
    poll1 = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth())
    task1_uuid = poll1.json()["tasks"][0]["id"]
    await client.put(f"/api/v1/tasks/{task1_uuid}", json={"status": "running"}, headers=auth())
    await client.post(
        f"/api/v1/tasks/{task1_uuid}/result",
        json={
            "exit_code": 0,
            "stdout": "step 1 done",
            "stderr": "",
            "session_id": "sess-resume-001",
            "work_dir": "/tmp/work/multi",
        },
        headers=auth(),
    )

    # Trigger new task by updating issue status
    await client.put(
        f"/api/v1/issues/{issue_uuid}",
        json={"status": "in_progress"},
        headers=auth(),
    )

    # Second poll should return new task with prior session info
    poll2 = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth())
    new_task = next(
        (t for t in poll2.json()["tasks"] if t["status"] == "dispatched"), None
    )
    assert new_task is not None
    assert new_task["prior_session_id"] == "sess-resume-001"
    assert new_task["prior_work_dir"] == "/tmp/work/multi"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Delete issue cascades to cancel tasks
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_issue_delete_cancels_tasks(client, db_session):
    """Deleting an issue cancels all its active tasks."""
    machine_uuid = await register_machine(client, "cascade-machine")

    # Create issue and dispatch task
    issue_resp = await client.post(
        "/api/v1/issues",
        json={
            "title": "Will be deleted",
            "status": "todo",
            "assignee_type": "machine",
            "assignee_id": machine_uuid,
        },
        headers=auth(),
    )
    issue_uuid = issue_resp.json()["data"]["id"]

    # Poll to dispatch the task
    poll_resp = await client.get(f"/api/v1/machines/{machine_uuid}/poll", headers=auth())
    task_uuid = poll_resp.json()["tasks"][0]["id"]

    # Verify task is dispatched before deletion
    task_resp = await client.get(f"/api/v1/tasks/{task_uuid}", headers=auth())
    assert task_resp.json()["data"]["status"] == "dispatched"

    # Delete issue - should cancel tasks first
    del_resp = await client.delete(f"/api/v1/issues/{issue_uuid}", headers=auth())
    assert del_resp.status_code == 200

    # Task should be cancelled (issue_id may be null after issue deletion)
    task_resp = await client.get(f"/api/v1/tasks/{task_uuid}", headers=auth())
    assert task_resp.json()["data"]["status"] == "cancelled"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Issue without assignee -> no auto-dispatch
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_issue_without_assignee_no_dispatch(client, db_session):
    """Issue created without assignee should not auto-dispatch any task."""
    issue_resp = await client.post(
        "/api/v1/issues",
        json={"title": "Backlog item", "status": "todo"},
        headers=auth(),
    )
    assert issue_resp.status_code == 200
    issue_uuid = issue_resp.json()["data"]["id"]

    # No tasks should exist for this issue
    tasks_resp = await client.get(f"/api/v1/issues/{issue_uuid}/tasks", headers=auth())
    assert tasks_resp.status_code == 200
    assert len(tasks_resp.json()["data"]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Multiple machines, multiple issues, concurrent polling
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_multi_machine_concurrent(client, db_session):
    """Two machines each get their own assigned tasks."""
    m1_uuid = await register_machine(client, "multi-m1")
    m2_uuid = await register_machine(client, "multi-m2")

    # Create issues assigned to different machines
    i1 = await client.post(
        "/api/v1/issues",
        json={"title": "Task for M1", "status": "todo", "assignee_type": "machine", "assignee_id": m1_uuid},
        headers=auth(),
    )
    i2 = await client.post(
        "/api/v1/issues",
        json={"title": "Task for M2", "status": "todo", "assignee_type": "machine", "assignee_id": m2_uuid},
        headers=auth(),
    )

    # Each machine polls and gets its own task
    p1 = await client.get(f"/api/v1/machines/{m1_uuid}/poll", headers=auth())
    p2 = await client.get(f"/api/v1/machines/{m2_uuid}/poll", headers=auth())

    assert len(p1.json()["tasks"]) == 1
    assert len(p2.json()["tasks"]) == 1
    assert p1.json()["tasks"][0]["issue_id"] == i1.json()["data"]["id"]
    assert p2.json()["tasks"][0]["issue_id"] == i2.json()["data"]["id"]
    assert p1.json()["tasks"][0]["instruction"] == "Task for M1"
    assert p2.json()["tasks"][0]["instruction"] == "Task for M2"
