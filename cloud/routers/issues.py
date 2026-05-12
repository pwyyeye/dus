import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

logger = logging.getLogger(__name__)
from models import Issue, Task, Machine, Agent, Label, IssueLabel, IssueDependency, Comment, ChatSession
from models import ChatMessage
from schemas import (
    IssueCreate,
    IssueUpdate,
    IssueResponse,
    IssueListResponse,
    IssueDetailResponse,
    IssueStatus,
    TaskListResponse,
    ApiResponse,
    IssueDependencyCreate,
    IssueDependencyResponse,
    CommentResponse,
    LabelResponse,
    ChatMessageResponse,
    ChatSessionWithMessages,
)
from connection_manager import manager as ws_manager

router = APIRouter(prefix="/issues", tags=["issues"])


def _generate_issue_id() -> str:
    return f"issue-{uuid.uuid4().hex[:8]}"


@router.post("", response_model=ApiResponse)
async def create_issue(payload: IssueCreate, db: AsyncSession = Depends(get_db)):
    """Create a new issue. When assignee is a machine/agent and status is active, auto-dispatch task."""
    # Validate parent issue
    if payload.parent_issue_id:
        parent_stmt = select(Issue).where(Issue.id == payload.parent_issue_id)
        parent_result = await db.execute(parent_stmt)
        if not parent_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Parent issue not found")

    # Resolve assignee and target machine
    target_machine_id = None
    if payload.assignee_type and payload.assignee_id:
        if payload.assignee_type == "machine":
            stmt = select(Machine).where(Machine.id == payload.assignee_id)
            result = await db.execute(stmt)
            machine = result.scalar_one_or_none()
            if not machine:
                raise HTTPException(status_code=400, detail="Assignee machine not found")
            target_machine_id = machine.id
        elif payload.assignee_type == "agent":
            stmt = select(Agent).where(Agent.id == payload.assignee_id)
            result = await db.execute(stmt)
            agent = result.scalar_one_or_none()
            if not agent:
                raise HTTPException(status_code=400, detail="Assignee agent not found")
            if not agent.is_enabled:
                raise HTTPException(status_code=400, detail="Assignee agent is disabled")
            target_machine_id = agent.machine_id
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported assignee_type: {payload.assignee_type}")

    issue = Issue(
        issue_id=_generate_issue_id(),
        title=payload.title,
        description=payload.description,
        status=payload.status.value,
        priority=payload.priority.value,
        assignee_type=payload.assignee_type,
        assignee_id=payload.assignee_id,
        project_id=payload.project_id,
        parent_issue_id=payload.parent_issue_id,
        agent_cli_id=payload.agent_cli_id,
    )
    db.add(issue)
    await db.flush()

    # Attach labels
    if payload.label_ids:
        label_stmt = select(Label).where(Label.id.in_(payload.label_ids))
        label_result = await db.execute(label_stmt)
        labels = label_result.scalars().all()
        issue.labels = list(labels)

    # Auto-dispatch: if has a valid assignee and status is active, create a Task
    if target_machine_id and issue.status not in ("done", "cancelled"):
        # Create ChatSession for this issue's conversation history
        chat_session = ChatSession(issue_id=issue.id, status="active")
        db.add(chat_session)
        await db.flush()

        task = Task(
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            instruction=issue.description or issue.title,
            project_id=issue.project_id,
            target_machine_id=target_machine_id,
            issue_id=issue.id,
            agent_cli_id=issue.agent_cli_id,
            chat_session_id=chat_session.id,
            status="pending",
        )
        db.add(task)
        await db.flush()
    # Issue is in_progress but has no assignee → create unassigned task for any agent to claim
    elif issue.status == "in_progress" and not issue.assignee_id:
        # Reuse existing ChatSession if available, otherwise create one
        existing_session = next((s for s in issue.chat_sessions if s.status == "active"), None)
        chat_session = existing_session if existing_session else ChatSession(issue_id=issue.id, status="active")
        if not existing_session:
            db.add(chat_session)
            await db.flush()

        task = Task(
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            instruction=issue.description or issue.title,
            project_id=issue.project_id,
            target_machine_id=None,
            issue_id=issue.id,
            agent_cli_id=issue.agent_cli_id,
            chat_session_id=chat_session.id,
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

    try:
        issue_data = IssueResponse.model_validate(issue).model_dump(mode="json")
    except Exception as e:
        logger.error(f"Failed to serialize issue {issue.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal serialization error: {e}")

    return ApiResponse(data=issue_data, message="Issue created successfully")


@router.get("", response_model=ApiResponse)
async def list_issues(
    status: IssueStatus | None = None,
    project_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    label_id: uuid.UUID | None = None,
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
    if label_id:
        stmt = stmt.join(IssueLabel).where(IssueLabel.label_id == label_id)

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
    """Get issue details with execution history (tasks), sub-issues, labels, dependencies and comments."""
    stmt = (
        select(Issue)
        .options(
            joinedload(Issue.tasks),
            joinedload(Issue.sub_issues),
            joinedload(Issue.labels),
            joinedload(Issue.comments),
            joinedload(Issue.outgoing_deps),
            joinedload(Issue.incoming_deps),
        )
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
    resp.sub_issues = [IssueListResponse.model_validate(si) for si in issue.sub_issues]
    resp.labels = [LabelResponse.model_validate(l) for l in issue.labels]

    # Build dependency list with depends_on issue details
    deps = []
    for d in issue.outgoing_deps:
        dep_resp = IssueDependencyResponse.model_validate(d)
        dep_stmt = select(Issue).where(Issue.id == d.depends_on_issue_id)
        dep_result = await db.execute(dep_stmt)
        dep_issue = dep_result.scalar_one_or_none()
        if dep_issue:
            dep_resp.depends_on = IssueListResponse.model_validate(dep_issue)
        deps.append(dep_resp)
    for d in issue.incoming_deps:
        dep_resp = IssueDependencyResponse.model_validate(d)
        dep_resp.dependency_type = "blocked_by" if d.dependency_type == "blocks" else d.dependency_type
        dep_stmt = select(Issue).where(Issue.id == d.issue_id)
        dep_result = await db.execute(dep_stmt)
        dep_issue = dep_result.scalar_one_or_none()
        if dep_issue:
            dep_resp.depends_on = IssueListResponse.model_validate(dep_issue)
        deps.append(dep_resp)
    resp.dependencies = deps

    # Build comment tree
    comment_map = {c.id: CommentResponse.model_validate(c) for c in issue.comments}
    root_comments = []
    for c in issue.comments:
        cr = comment_map[c.id]
        if c.parent_id and c.parent_id in comment_map:
            comment_map[c.parent_id].replies.append(cr)
        else:
            root_comments.append(cr)
    resp.comments = sorted(root_comments, key=lambda x: x.created_at)

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
        new_status = payload.status.value
        # 状态流转校验：如果进入 in_progress，检查是否有未完成的 blocked_by 依赖
        if new_status == "in_progress":
            blocked_by_incomplete = []
            for d in issue.incoming_deps:
                if d.dependency_type == "blocks":
                    dep_stmt = select(Issue).where(Issue.id == d.issue_id)
                    dep_result = await db.execute(dep_stmt)
                    dep_issue = dep_result.scalar_one_or_none()
                    if dep_issue and dep_issue.status not in ("done", "cancelled"):
                        blocked_by_incomplete.append(dep_issue.issue_id)
            if blocked_by_incomplete:
                raise HTTPException(
                    status_code=409,
                    detail=f"Issue is blocked by incomplete issues: {', '.join(blocked_by_incomplete)}",
                )
        issue.status = new_status
    if payload.priority is not None:
        issue.priority = payload.priority.value
    if payload.assignee_type is not None:
        issue.assignee_type = payload.assignee_type
    if payload.assignee_id is not None:
        issue.assignee_id = payload.assignee_id
    if payload.project_id is not None:
        issue.project_id = payload.project_id
    if payload.agent_cli_id is not None:
        issue.agent_cli_id = payload.agent_cli_id
    if payload.parent_issue_id is not None:
        # Prevent self-reference and circular reference
        if payload.parent_issue_id == issue_uuid:
            raise HTTPException(status_code=400, detail="Issue cannot be its own parent")
        if payload.parent_issue_id:
            parent_stmt = select(Issue).where(Issue.id == payload.parent_issue_id)
            parent_result = await db.execute(parent_stmt)
            if not parent_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Parent issue not found")
        issue.parent_issue_id = payload.parent_issue_id
    if payload.label_ids is not None:
        if payload.label_ids:
            label_stmt = select(Label).where(Label.id.in_(payload.label_ids))
            label_result = await db.execute(label_stmt)
            issue.labels = list(label_result.scalars().all())
        else:
            issue.labels = []

    issue.updated_at = datetime.now(timezone.utc)

    # Reconcile tasks when assignee changes
    assignee_changed = prev_assignee_id != issue.assignee_id
    status_changed = prev_status != issue.status

    if assignee_changed or (status_changed and issue.status not in ("done", "cancelled")):
        for task in issue.tasks:
            if task.status in ("pending", "dispatched"):
                task.status = "cancelled"

        target_machine_id = None
        if issue.assignee_type and issue.assignee_id and issue.status not in ("done", "cancelled"):
            if issue.assignee_type == "machine":
                target_machine_id = issue.assignee_id
            elif issue.assignee_type == "agent":
                agent_stmt = select(Agent).where(Agent.id == issue.assignee_id)
                agent_result = await db.execute(agent_stmt)
                agent_obj = agent_result.scalar_one_or_none()
                if agent_obj and agent_obj.is_enabled:
                    target_machine_id = agent_obj.machine_id

        if target_machine_id:
            new_task = Task(
                task_id=f"task-{uuid.uuid4().hex[:8]}",
                instruction=issue.description or issue.title,
                project_id=issue.project_id,
                target_machine_id=target_machine_id,
                issue_id=issue.id,
                agent_cli_id=issue.agent_cli_id,
                status="pending",
            )
            db.add(new_task)
            await db.flush()
            logger.info(f"Created task for issue {issue.issue_id} with target_machine_id={target_machine_id}")
        # Issue 进入 in_progress 但无 assignee → 创建待认领任务到任务池
        elif issue.status == "in_progress" and not issue.assignee_id:
            has_pending_task = any(t.status in ("pending", "dispatched") for t in issue.tasks)
            logger.info(f"Issue {issue.issue_id} is in_progress with no assignee, checking for existing tasks")
            if not has_pending_task:
                new_task = Task(
                    task_id=f"task-{uuid.uuid4().hex[:8]}",
                    instruction=issue.description or issue.title,
                    project_id=issue.project_id,
                    target_machine_id=None,  # 无机器分配，等待任意 agent 认领
                    issue_id=issue.id,
                    agent_cli_id=issue.agent_cli_id,
                    status="pending",
                )
                db.add(new_task)
                await db.flush()
                logger.info(f"Created unassigned task {new_task.task_id} for in_progress issue {issue.issue_id}")

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


# ── Issue Dependencies ──


@router.post("/{issue_uuid}/dependencies", response_model=ApiResponse)
async def add_issue_dependency(
    issue_uuid: uuid.UUID,
    payload: IssueDependencyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a dependency between this issue and another issue."""
    if issue_uuid == payload.depends_on_issue_id:
        raise HTTPException(status_code=400, detail="An issue cannot depend on itself")

    # Verify both issues exist
    stmt = select(Issue).where(Issue.id == issue_uuid)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Issue not found")

    dep_stmt = select(Issue).where(Issue.id == payload.depends_on_issue_id)
    dep_result = await db.execute(dep_stmt)
    if not dep_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Depends-on issue not found")

    # Check duplicate
    dup_stmt = select(IssueDependency).where(
        IssueDependency.issue_id == issue_uuid,
        IssueDependency.depends_on_issue_id == payload.depends_on_issue_id,
    )
    dup_result = await db.execute(dup_stmt)
    if dup_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Dependency already exists")

    dep = IssueDependency(
        issue_id=issue_uuid,
        depends_on_issue_id=payload.depends_on_issue_id,
        dependency_type=payload.dependency_type.value,
    )
    db.add(dep)
    await db.flush()

    return ApiResponse(
        data=IssueDependencyResponse.model_validate(dep).model_dump(mode="json"),
        message="Dependency added",
    )


@router.delete("/{issue_uuid}/dependencies/{dep_id}", response_model=ApiResponse)
async def remove_issue_dependency(
    issue_uuid: uuid.UUID,
    dep_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a dependency."""
    stmt = select(IssueDependency).where(
        IssueDependency.id == dep_id,
        IssueDependency.issue_id == issue_uuid,
    )
    result = await db.execute(stmt)
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependency not found")

    await db.delete(dep)
    await db.flush()
    return ApiResponse(message="Dependency removed")


# ── Chat History ──


@router.get("/{issue_uuid}/messages", response_model=ApiResponse)
async def list_issue_messages(
    issue_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all chat messages for an issue's conversation history."""
    stmt = select(Issue).options(joinedload(Issue.chat_sessions)).where(Issue.id == issue_uuid)
    result = await db.execute(stmt)
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if not issue.chat_sessions:
        return ApiResponse(data=[])

    # Get the most recent active session
    active_session = None
    for session in issue.chat_sessions:
        if session.status == "active":
            active_session = session
            break
    if not active_session:
        # Return most recent session if no active one
        active_session = max(issue.chat_sessions, key=lambda s: s.created_at)

    messages = [
        ChatMessageResponse.model_validate(m).model_dump(mode="json")
        for m in active_session.messages
    ]

    return ApiResponse(data=messages)
