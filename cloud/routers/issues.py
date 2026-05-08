import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Issue, Task, Machine
from schemas import (
    IssueCreate,
    IssueUpdate,
    IssueResponse,
    IssueListResponse,
    IssueDetailResponse,
    IssueStatus,
    TaskListResponse,
    ApiResponse,
)
from connection_manager import manager as ws_manager

router = APIRouter(prefix="/issues", tags=["issues"])


def _generate_issue_id() -> str:
    return f"issue-{uuid.uuid4().hex[:8]}"


@router.post("", response_model=ApiResponse)
async def create_issue(payload: IssueCreate, db: AsyncSession = Depends(get_db)):
    """Create a new issue. When assignee is a machine and status is active, auto-dispatch task."""
    # Validate assignee if provided
    if payload.assignee_type == "machine" and payload.assignee_id:
        stmt = select(Machine).where(Machine.id == payload.assignee_id)
        result = await db.execute(stmt)
        machine = result.scalar_one_or_none()
        if not machine:
            raise HTTPException(status_code=400, detail="Assignee machine not found")

    issue = Issue(
        issue_id=_generate_issue_id(),
        title=payload.title,
        description=payload.description,
        status=payload.status.value,
        priority=payload.priority.value,
        assignee_type=payload.assignee_type,
        assignee_id=payload.assignee_id,
        project_id=payload.project_id,
    )
    db.add(issue)
    await db.flush()

    # Auto-dispatch: if assigned to a machine and status is not done/cancelled,
    # create a Task from the Issue.
    if (
        issue.assignee_type == "machine"
        and issue.assignee_id
        and issue.status not in ("done", "cancelled")
    ):
        task = Task(
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            instruction=issue.title + (f"\n\n{issue.description}" if issue.description else ""),
            project_id=issue.project_id,
            target_machine_id=issue.assignee_id,
            issue_id=issue.id,
            status="pending",
        )
        db.add(task)
        await db.flush()

    try:
        await ws_manager.broadcast(
            "issue.created",
            {"id": str(issue.id), "status": issue.status, "issue_id": issue.issue_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=IssueResponse.model_validate(issue).model_dump(mode="json"),
        message="Issue created successfully",
    )


@router.get("", response_model=ApiResponse)
async def list_issues(
    status: IssueStatus | None = None,
    project_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List issues with optional filters and pagination."""
    stmt = select(Issue)
    if status:
        stmt = stmt.where(Issue.status == status.value)
    if project_id:
        stmt = stmt.where(Issue.project_id == project_id)
    if assignee_id:
        stmt = stmt.where(Issue.assignee_id == assignee_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = stmt.order_by(Issue.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    issues = result.scalars().all()

    return ApiResponse(
        data=[IssueListResponse.model_validate(i).model_dump(mode="json") for i in issues],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/{issue_uuid}", response_model=ApiResponse)
async def get_issue(issue_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get issue details with execution history (tasks)."""
    stmt = (
        select(Issue)
        .options(joinedload(Issue.tasks))
        .where(Issue.id == issue_uuid)
    )
    result = await db.execute(stmt)
    issue = result.unique().scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    resp = IssueDetailResponse.model_validate(issue)
    resp.tasks = [
        TaskListResponse.model_validate(t) for t in sorted(issue.tasks, key=lambda x: x.created_at, reverse=True)
    ]

    return ApiResponse(data=resp.model_dump(mode="json"))


@router.put("/{issue_uuid}", response_model=ApiResponse)
async def update_issue(
    issue_uuid: uuid.UUID, payload: IssueUpdate, db: AsyncSession = Depends(get_db)
):
    """Update issue. When assignee/status changes, reconcile tasks."""
    stmt = select(Issue).options(joinedload(Issue.tasks)).where(Issue.id == issue_uuid)
    result = await db.execute(stmt)
    issue = result.unique().scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    prev_status = issue.status
    prev_assignee_id = issue.assignee_id

    if payload.title is not None:
        issue.title = payload.title
    if payload.description is not None:
        issue.description = payload.description
    if payload.status is not None:
        issue.status = payload.status.value
    if payload.priority is not None:
        issue.priority = payload.priority.value
    if payload.assignee_type is not None:
        issue.assignee_type = payload.assignee_type
    if payload.assignee_id is not None:
        issue.assignee_id = payload.assignee_id
    if payload.project_id is not None:
        issue.project_id = payload.project_id

    issue.updated_at = datetime.now(timezone.utc)

    # Reconcile tasks when assignee changes
    assignee_changed = prev_assignee_id != issue.assignee_id
    status_changed = prev_status != issue.status

    if assignee_changed or (status_changed and issue.status not in ("done", "cancelled")):
        # Cancel pending/dispatched tasks for this issue
        for task in issue.tasks:
            if task.status in ("pending", "dispatched"):
                task.status = "cancelled"

        # Auto-create new task if assignee is a machine and issue is active
        if (
            issue.assignee_type == "machine"
            and issue.assignee_id
            and issue.status not in ("done", "cancelled")
        ):
            new_task = Task(
                task_id=f"task-{uuid.uuid4().hex[:8]}",
                instruction=issue.title + (f"\n\n{issue.description}" if issue.description else ""),
                project_id=issue.project_id,
                target_machine_id=issue.assignee_id,
                issue_id=issue.id,
                status="pending",
            )
            db.add(new_task)
            await db.flush()

    # Cancel active tasks when issue is cancelled
    if status_changed and issue.status == "cancelled":
        for task in issue.tasks:
            if task.status in ("pending", "dispatched", "running"):
                task.status = "cancelled"

    try:
        await ws_manager.broadcast(
            "issue.updated",
            {"id": str(issue.id), "status": issue.status, "issue_id": issue.issue_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=IssueResponse.model_validate(issue).model_dump(mode="json"),
        message="Issue updated successfully",
    )


@router.delete("/{issue_uuid}", response_model=ApiResponse)
async def delete_issue(issue_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete issue and cascade cancel its tasks."""
    stmt = select(Issue).options(joinedload(Issue.tasks)).where(Issue.id == issue_uuid)
    result = await db.execute(stmt)
    issue = result.unique().scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Cancel all active tasks first
    for task in issue.tasks:
        if task.status in ("pending", "dispatched", "running"):
            task.status = "cancelled"

    await db.delete(issue)
    await db.flush()

    try:
        await ws_manager.broadcast(
            "issue.deleted",
            {"id": str(issue_uuid), "issue_id": issue.issue_id},
        )
    except Exception:
        pass

    return ApiResponse(message="Issue deleted successfully")


@router.get("/{issue_uuid}/tasks", response_model=ApiResponse)
async def list_issue_tasks(
    issue_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all tasks belonging to an issue (execution history)."""
    stmt = select(Issue).where(Issue.id == issue_uuid)
    result = await db.execute(stmt)
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    tasks_stmt = (
        select(Task)
        .where(Task.issue_id == issue_uuid)
        .order_by(Task.created_at.desc())
    )
    tasks_result = await db.execute(tasks_stmt)
    tasks = tasks_result.scalars().all()

    return ApiResponse(
        data=[TaskListResponse.model_validate(t).model_dump(mode="json") for t in tasks]
    )
