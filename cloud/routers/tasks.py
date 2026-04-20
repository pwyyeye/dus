import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Task, Machine
from schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResultSubmit,
    TaskResponse,
    TaskListResponse,
    TaskStatus,
    ApiResponse,
)

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

    task = Task(
        task_id=_generate_task_id(),
        instruction=payload.instruction,
        target_machine_id=payload.target_machine_id,
        project_id=payload.project_id,
    )
    db.add(task)
    await db.flush()

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
    task.completed_at = now
    task.result = {
        "exit_code": payload.exit_code,
        "stdout": payload.stdout,
        "stderr": payload.stderr,
        "error_type": payload.error_type,
    }

    if payload.error_type:
        task.status = "failed"
        task.error_message = payload.stderr or payload.error_type
    else:
        task.status = "completed"

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
    task.completed_at = now
    task.result = {
        "exit_code": payload.exit_code,
        "stdout": payload.stdout,
        "stderr": payload.stderr,
        "error_type": payload.error_type,
    }

    if payload.error_type:
        task.status = "failed"
        task.error_message = payload.stderr or payload.error_type
    else:
        task.status = "completed"

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Callback received",
    )


@router.post("/{task_uuid}/remind", response_model=ApiResponse)
async def trigger_reminder(task_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Trigger a reminder for manual_only tasks (called by Bridge)."""
    stmt = select(Task).where(Task.id == task_uuid)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "pending_manual"

    return ApiResponse(
        data=TaskResponse.model_validate(task).model_dump(mode="json"),
        message="Reminder triggered",
    )
