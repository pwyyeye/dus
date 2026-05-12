import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models import Task, Machine, Issue, TaskLog, ChatSession, ChatMessage
from notifier import send_wechat_markdown
from schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResultSubmit,
    TaskProgressSubmit,
    TaskResponse,
    TaskListResponse,
    TaskLogResponse,
    TaskStatus,
    ApiResponse,
    ChatMessageCreate,
    ChatMessageResponse,
)
from connection_manager import manager as ws_manager

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _generate_task_id() -> str:
    return f"task-{uuid.uuid4().hex[:8]}"


@router.post("", response_model=ApiResponse)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Create a new task with instruction and project binding."""
    if payload.target_machine_id:
        stmt = select(Machine).where(Machine.id == payload.target_machine_id)
        result = await db.execute(stmt)
        machine = result.scalar_one_or_none()
        if not machine:
            raise HTTPException(status_code=400, detail="Target machine not found")

    if payload.issue_id:
        stmt = select(Issue).where(Issue.id == payload.issue_id)
        result = await db.execute(stmt)
        issue = result.scalar_one_or_none()
        if not issue:
            raise HTTPException(status_code=400, detail="Issue not found")

    task = Task(
        task_id=_generate_task_id(),
        instruction=payload.instruction,
        target_machine_id=payload.target_machine_id,
        project_id=payload.project_id,
        issue_id=payload.issue_id,
        agent_cli_id=payload.agent_cli_id,
        max_retries=payload.max_retries,
    )
    db.add(task)
    await db.flush()

    log = TaskLog(task_id=task.id, event_type="created", message="Task created")
    db.add(log)

    try:
        await ws_manager.broadcast(
            "task.created",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Task created successfully",
    )


@router.get("", response_model=ApiResponse)
async def list_tasks(
    status: TaskStatus | None = None,
    project_id: uuid.UUID | None = None,
    target_machine_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List tasks with optional filters and pagination."""
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status.value)
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    if target_machine_id:
        stmt = stmt.where(Task.target_machine_id == target_machine_id)

    stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return ApiResponse(
        data=[TaskListResponse.model_validate(t).model_dump(mode="json") for t in tasks]
    )


@router.get("/pool", response_model=ApiResponse)
async def list_unassigned_tasks(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List unassigned pending tasks (task pool for auto-claim)."""
    stmt = select(Task).where(
        Task.target_machine_id.is_(None),
        Task.status == "pending",
    ).order_by(Task.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return ApiResponse(
        data=[TaskListResponse.model_validate(t).model_dump(mode="json") for t in tasks]
    )


@router.get("/{task_uuid}", response_model=ApiResponse)
async def get_task(task_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get task details."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return ApiResponse(data=TaskResponse.model_validate(task).model_dump(mode="json"))


@router.put("/{task_uuid}", response_model=ApiResponse)
async def update_task(
    task_uuid: uuid.UUID, payload: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    """Update task status."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now(timezone.utc)

    if payload.status:
        new_status = payload.status.value
        allowed = {
            "pending": ["dispatched", "cancelled"],
            "dispatched": ["running", "cancelled"],
            "running": ["completed", "failed", "cancelled"],
            "pending_manual": ["completed", "cancelled"],
        }
        current_allowed = allowed.get(task.status, [])
        if new_status not in current_allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from '{task.status}' to '{new_status}'",
            )

        task.status = new_status

        if new_status == "running":
            task.started_at = now
        elif new_status in ("completed", "failed", "cancelled"):
            task.completed_at = now

    try:
        await ws_manager.broadcast(
            "task.updated",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Task updated successfully",
    )


@router.post("/{task_uuid}/result", response_model=ApiResponse)
async def submit_result(
    task_uuid: uuid.UUID, payload: TaskResultSubmit, db: AsyncSession = Depends(get_db)
):
    """Bridge or device submits execution result."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now(timezone.utc)
    task.result = {
        "exit_code": payload.exit_code,
        "stdout": payload.stdout,
        "stderr": payload.stderr,
        "error_type": payload.error_type,
    }
    if payload.session_id is not None:
        task.session_id = payload.session_id
    if payload.work_dir is not None:
        task.work_dir = payload.work_dir

    if payload.error_type:
        # Check retry eligibility
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = "pending"
            task.error_message = None
            log = TaskLog(
                task_id=task.id,
                event_type="retrying",
                message=f"Retry {task.retry_count}/{task.max_retries}: {payload.stderr or payload.error_type}",
            )
            db.add(log)
        else:
            task.status = "failed"
            task.completed_at = now
            task.error_message = payload.stderr or payload.error_type
            log = TaskLog(
                task_id=task.id,
                event_type="failed",
                message=task.error_message,
            )
            db.add(log)
    else:
        task.status = "completed"
        task.completed_at = now
        log = TaskLog(
            task_id=task.id,
            event_type="completed",
            message=f"Exit code: {payload.exit_code}",
        )
        db.add(log)

    # Sync issue status when task finishes
    if task.issue_id and task.status in ("completed", "failed"):
        issue_stmt = select(Issue).where(Issue.id == task.issue_id)
        issue_result = await db.execute(issue_stmt)
        issue = issue_result.scalar_one_or_none()
        if issue:
            if task.status == "completed":
                issue.status = "done"
            elif task.status == "failed":
                issue.status = "todo"
            issue.updated_at = now
            try:
                await ws_manager.broadcast(
                    "issue.updated",
                    {"id": str(issue.id), "status": issue.status, "issue_id": issue.issue_id},
                )
            except Exception:
                pass

    try:
        await ws_manager.broadcast(
            "task.updated",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Result submitted successfully",
    )


@router.post("/{task_uuid}/callback", response_model=ApiResponse)
async def task_callback(
    task_uuid: uuid.UUID,
    payload: TaskResultSubmit,
    db: AsyncSession = Depends(get_db),
):
    """Device callback to report task execution result via hook script."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now(timezone.utc)
    task.result = {
        "exit_code": payload.exit_code,
        "stdout": payload.stdout,
        "stderr": payload.stderr,
        "error_type": payload.error_type,
    }
    if payload.session_id is not None:
        task.session_id = payload.session_id
    if payload.work_dir is not None:
        task.work_dir = payload.work_dir

    if payload.error_type:
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = "pending"
            task.error_message = None
            log = TaskLog(
                task_id=task.id,
                event_type="retrying",
                message=f"Retry {task.retry_count}/{task.max_retries}: {payload.stderr or payload.error_type}",
            )
            db.add(log)
        else:
            task.status = "failed"
            task.completed_at = now
            task.error_message = payload.stderr or payload.error_type
            log = TaskLog(
                task_id=task.id,
                event_type="failed",
                message=task.error_message,
            )
            db.add(log)
    else:
        task.status = "completed"
        task.completed_at = now
        log = TaskLog(
            task_id=task.id,
            event_type="completed",
            message=f"Exit code: {payload.exit_code}",
        )
        db.add(log)

    try:
        await ws_manager.broadcast(
            "task.updated",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Callback received",
    )


@router.put("/{task_uuid}/pin", response_model=ApiResponse)
async def pin_task_session(
    task_uuid: uuid.UUID,
    payload: TaskResultSubmit,
    db: AsyncSession = Depends(get_db),
):
    """Bridge pins session_id and work_dir mid-run for crash recovery.
    Inspired by Multica PinTaskSession.
    """
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if payload.session_id is not None:
        task.session_id = payload.session_id
    if payload.work_dir is not None:
        task.work_dir = payload.work_dir

    try:
        await ws_manager.broadcast(
            "task.updated",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Session pinned",
    )


@router.post("/{task_uuid}/progress", response_model=ApiResponse)
async def submit_progress(
    task_uuid: uuid.UUID,
    payload: TaskProgressSubmit,
    db: AsyncSession = Depends(get_db),
):
    """Bridge submits incremental stdout/stderr during execution."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Append delta to progress_output
    current = task.progress_output or ""
    if payload.stdout_delta:
        current += payload.stdout_delta
    if payload.stderr_delta:
        current += payload.stderr_delta
    task.progress_output = current[-50000:]  # cap at 50KB

    try:
        await ws_manager.broadcast(
            "task.progress",
            {
                "id": str(task.id),
                "task_id": task.task_id,
                "stdout_delta": payload.stdout_delta,
                "stderr_delta": payload.stderr_delta,
                "progress_pct": payload.progress_pct,
            },
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Progress received",
    )


@router.post("/{task_uuid}/remind", response_model=ApiResponse)
async def trigger_reminder(task_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Trigger a reminder for manual_only tasks (called by Bridge)."""
    stmt = select(Task).options(
        joinedload(Task.target_machine),
        joinedload(Task.project),
    ).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "pending_manual"

    # Send WeChat notification
    settings = get_settings()
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    task_link = f"{frontend_url}/tasks/{task.task_id}"

    machine_name = task.target_machine.machine_name if task.target_machine else "Unknown"
    project_name = task.project.project_name if task.project else "Unknown"
    project_root = task.project.root_path if task.project else "Unknown"

    message_content = (
        f"**任务指令**: {task.instruction}\n\n"
        f"**所属机器**: {machine_name}\n"
        f"**项目名称**: {project_name}\n"
        f"**项目路径**: {project_root}\n\n"
        f"完成后请手动标记任务完成: [查看任务]({task_link})"
    )

    await send_wechat_markdown(title="⚠️ 手动任务提醒", content=message_content)

    try:
        await ws_manager.broadcast(
            "task.updated",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Reminder triggered",
    )


@router.post("/{task_uuid}/claim", response_model=ApiResponse)
async def claim_task(
    task_uuid: uuid.UUID,
    machine_uuid: uuid.UUID = Query(..., description="Machine UUID claiming the task"),
    db: AsyncSession = Depends(get_db),
):
    """Claim an unassigned pending task. Only allowed if the task belongs to the machine's project."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.target_machine_id is not None:
        raise HTTPException(status_code=400, detail="Task already assigned to a machine")

    if task.status != "pending":
        raise HTTPException(status_code=400, detail=f"Task is '{task.status}', cannot claim")

    stmt = select(Machine).where(Machine.id == machine_uuid)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if task.project_id != machine.project_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot claim tasks outside your project scope",
        )

    task.target_machine_id = machine_uuid
    task.status = "dispatched"

    try:
        await ws_manager.broadcast(
            "task.updated",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=TaskListResponse.model_validate(task).model_dump(mode="json"),
        message="Task claimed successfully",
    )


# ── Task Logs ──


@router.get("/{task_uuid}/logs", response_model=ApiResponse)
async def list_task_logs(
    task_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all logs for a task (event history)."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    logs_stmt = (
        select(TaskLog)
        .where(TaskLog.task_id == task_uuid)
        .order_by(TaskLog.created_at.desc())
    )
    logs_result = await db.execute(logs_stmt)
    logs = logs_result.scalars().all()

    return ApiResponse(
        data=[TaskLogResponse.model_validate(l).model_dump(mode="json") for l in logs]
    )


# ── Chat Messages ──


@router.post("/{task_uuid}/messages", response_model=ApiResponse)
async def append_chat_message(
    task_uuid: uuid.UUID,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Append a message to the chat session associated with a task.

    Called by Bridge during agent execution to record conversation history.
    """
    # Get task and its chat_session
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.chat_session_id:
        raise HTTPException(status_code=400, detail="Task has no associated chat session")

    # Create the message
    chat_message = ChatMessage(
        chat_session_id=task.chat_session_id,
        role=payload.role,
        content=payload.content,
        task_id=task_uuid,
    )
    db.add(chat_message)
    await db.commit()

    return ApiResponse(
        data=ChatMessageResponse.model_validate(chat_message).model_dump(mode="json"),
        message="Message appended",
    )
