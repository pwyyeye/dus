import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Autopilot, Task, Machine, TaskLog
from schemas import (
    AutopilotCreate,
    AutopilotUpdate,
    AutopilotResponse,
    ApiResponse,
)
from connection_manager import manager as ws_manager

router = APIRouter(prefix="/autopilots", tags=["autopilots"])


def _compute_next_run(trigger_type: str, cron_expr: str | None, interval_minutes: int | None) -> datetime | None:
    """Compute next run time based on trigger config."""
    now = datetime.now(timezone.utc)
    if trigger_type == "interval" and interval_minutes:
        return now + timedelta(minutes=interval_minutes)
    # cron not implemented here - would need croniter library
    return None


@router.post("", response_model=ApiResponse)
async def create_autopilot(payload: AutopilotCreate, db: AsyncSession = Depends(get_db)):
    """Create an autopilot (scheduled task creator)."""
    if payload.template_id:
        from models import TaskTemplate
        stmt = select(TaskTemplate).where(TaskTemplate.id == payload.template_id)
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Template not found")

    if payload.target_machine_id:
        stmt = select(Machine).where(Machine.id == payload.target_machine_id)
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Target machine not found")

    autopilot = Autopilot(
        name=payload.name,
        description=payload.description,
        project_id=payload.project_id,
        template_id=payload.template_id,
        target_machine_id=payload.target_machine_id,
        trigger_type=payload.trigger_type,
        cron_expr=payload.cron_expr,
        interval_minutes=payload.interval_minutes,
        webhook_secret=payload.webhook_secret,
        next_run_at=_compute_next_run(payload.trigger_type, payload.cron_expr, payload.interval_minutes),
    )
    db.add(autopilot)
    await db.flush()

    return ApiResponse(
        data=AutopilotResponse.model_validate(autopilot).model_dump(mode="json"),
        message="Autopilot created",
    )


@router.get("", response_model=ApiResponse)
async def list_autopilots(
    project_id: uuid.UUID | None = None,
    is_enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List autopilots with optional filters."""
    stmt = select(Autopilot)
    if project_id:
        stmt = stmt.where(Autopilot.project_id == project_id)
    if is_enabled is not None:
        stmt = stmt.where(Autopilot.is_enabled == is_enabled)

    stmt = stmt.order_by(Autopilot.created_at.desc())
    result = await db.execute(stmt)
    autopilots = result.scalars().all()

    return ApiResponse(
        data=[AutopilotResponse.model_validate(a).model_dump(mode="json") for a in autopilots]
    )


@router.get("/{autopilot_id}", response_model=ApiResponse)
async def get_autopilot(autopilot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get autopilot details."""
    stmt = select(Autopilot).where(Autopilot.id == autopilot_id)
    result = await db.execute(stmt)
    autopilot = result.scalar_one_or_none()
    if not autopilot:
        raise HTTPException(status_code=404, detail="Autopilot not found")

    return ApiResponse(
        data=AutopilotResponse.model_validate(autopilot).model_dump(mode="json")
    )


@router.put("/{autopilot_id}", response_model=ApiResponse)
async def update_autopilot(
    autopilot_id: uuid.UUID,
    payload: AutopilotUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an autopilot."""
    stmt = select(Autopilot).where(Autopilot.id == autopilot_id)
    result = await db.execute(stmt)
    autopilot = result.scalar_one_or_none()
    if not autopilot:
        raise HTTPException(status_code=404, detail="Autopilot not found")

    if payload.name is not None:
        autopilot.name = payload.name
    if payload.description is not None:
        autopilot.description = payload.description
    if payload.project_id is not None:
        autopilot.project_id = payload.project_id
    if payload.template_id is not None:
        autopilot.template_id = payload.template_id
    if payload.target_machine_id is not None:
        autopilot.target_machine_id = payload.target_machine_id
    if payload.trigger_type is not None:
        autopilot.trigger_type = payload.trigger_type
    if payload.cron_expr is not None:
        autopilot.cron_expr = payload.cron_expr
    if payload.interval_minutes is not None:
        autopilot.interval_minutes = payload.interval_minutes
    if payload.is_enabled is not None:
        autopilot.is_enabled = payload.is_enabled

    autopilot.next_run_at = _compute_next_run(
        autopilot.trigger_type, autopilot.cron_expr, autopilot.interval_minutes
    )
    autopilot.updated_at = datetime.now(timezone.utc)

    return ApiResponse(
        data=AutopilotResponse.model_validate(autopilot).model_dump(mode="json"),
        message="Autopilot updated",
    )


@router.delete("/{autopilot_id}", response_model=ApiResponse)
async def delete_autopilot(autopilot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete an autopilot."""
    stmt = select(Autopilot).where(Autopilot.id == autopilot_id)
    result = await db.execute(stmt)
    autopilot = result.scalar_one_or_none()
    if not autopilot:
        raise HTTPException(status_code=404, detail="Autopilot not found")

    await db.delete(autopilot)
    await db.flush()
    return ApiResponse(message="Autopilot deleted")


@router.post("/{autopilot_id}/run", response_model=ApiResponse)
async def trigger_autopilot(autopilot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Manually trigger an autopilot to create a task now."""
    stmt = select(Autopilot).where(Autopilot.id == autopilot_id)
    result = await db.execute(stmt)
    autopilot = result.scalar_one_or_none()
    if not autopilot:
        raise HTTPException(status_code=404, detail="Autopilot not found")

    if not autopilot.is_enabled:
        raise HTTPException(status_code=400, detail="Autopilot is disabled")

    # Build instruction from template or autopilot description
    instruction = autopilot.description or autopilot.name
    if autopilot.template_id:
        from models import TaskTemplate
        tpl_stmt = select(TaskTemplate).where(TaskTemplate.id == autopilot.template_id)
        tpl_result = await db.execute(tpl_stmt)
        template = tpl_result.scalar_one_or_none()
        if template:
            instruction = template.instruction

    task = Task(
        task_id=f"task-{uuid.uuid4().hex[:8]}",
        instruction=instruction,
        project_id=autopilot.project_id,
        target_machine_id=autopilot.target_machine_id,
        template_id=autopilot.template_id,
    )
    db.add(task)

    # Log
    log = TaskLog(
        task_id=task.id,
        event_type="created",
        message=f"Created by autopilot: {autopilot.name}",
    )
    db.add(log)

    # Update autopilot runtime
    autopilot.last_run_at = datetime.now(timezone.utc)
    autopilot.run_count += 1
    autopilot.next_run_at = _compute_next_run(
        autopilot.trigger_type, autopilot.cron_expr, autopilot.interval_minutes
    )

    await db.flush()

    try:
        await ws_manager.broadcast(
            "task.created",
            {"id": str(task.id), "status": task.status, "task_id": task.task_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=AutopilotResponse.model_validate(autopilot).model_dump(mode="json"),
        message=f"Task created: {task.task_id}",
    )


@router.post("/webhook/{webhook_secret}", response_model=ApiResponse)
async def webhook_trigger(webhook_secret: str, db: AsyncSession = Depends(get_db)):
    """Trigger autopilot via webhook (POST with secret in URL)."""
    stmt = select(Autopilot).where(
        Autopilot.webhook_secret == webhook_secret,
        Autopilot.is_enabled == True,
        Autopilot.trigger_type == "webhook",
    )
    result = await db.execute(stmt)
    autopilot = result.scalar_one_or_none()
    if not autopilot:
        raise HTTPException(status_code=404, detail="No matching autopilot found")

    # Reuse the run logic
    return await trigger_autopilot(autopilot.id, db)
