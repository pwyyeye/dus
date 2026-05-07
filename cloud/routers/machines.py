import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Machine, Task, Project
from schemas import (
    MachineCreate,
    MachineResponse,
    MachineListResponse,
    MachineStatus,
    AgentStatus,
    AgentType,
    ApiResponse,
    PollResponse,
    PollTaskResponse,
    MachineUpdateStatus,
    MachineDashboardResponse,
    TaskListResponse,
)

router = APIRouter(prefix="/machines", tags=["machines"])


@router.post("", response_model=ApiResponse)
async def register_machine(payload: MachineCreate, db: AsyncSession = Depends(get_db)):
    """Register a new machine or update existing one. Auto-creates project if not exists."""
    # Auto-create project if project_id is provided and doesn't exist
    resolved_project_id = None
    if payload.project_id:
        stmt = select(Project).where(Project.project_id == payload.project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            project = Project(
                project_id=payload.project_id,
                project_name=payload.project_id,
            )
            db.add(project)
            await db.flush()
        resolved_project_id = project.id

    stmt = select(Machine).where(Machine.machine_id == payload.machine_id)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()

    if machine:
        machine.machine_name = payload.machine_name
        machine.agent_type = payload.agent_type.value
        machine.agent_capability = payload.agent_capability.value
        machine.agent_version = payload.agent_version
        machine.status = "online"
        machine.project_id = resolved_project_id or machine.project_id
        machine.last_poll_at = datetime.now(timezone.utc)
    else:
        machine = Machine(
            machine_id=payload.machine_id,
            machine_name=payload.machine_name,
            agent_type=payload.agent_type.value,
            agent_capability=payload.agent_capability.value,
            agent_version=payload.agent_version,
            status="online",
            project_id=resolved_project_id,
            last_poll_at=datetime.now(timezone.utc),
        )
        db.add(machine)

    await db.flush()

    return ApiResponse(
        data=MachineListResponse.model_validate(machine).model_dump(mode="json"),
        message="Machine registered successfully",
    )


@router.get("", response_model=ApiResponse)
async def list_machines(
    status: MachineStatus | None = None,
    agent_type: AgentType | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all machines with optional filters."""
    stmt = select(Machine)
    if status:
        stmt = stmt.where(Machine.status == status.value)
    if agent_type:
        stmt = stmt.where(Machine.agent_type == agent_type.value)
    stmt = stmt.order_by(Machine.registered_at.desc())

    result = await db.execute(stmt)
    machines = result.scalars().all()

    return ApiResponse(
        data=[MachineListResponse.model_validate(m).model_dump(mode="json") for m in machines]
    )


@router.get("/dashboard", response_model=ApiResponse)
async def get_machines_dashboard(db: AsyncSession = Depends(get_db)):
    """Get all machines with their running tasks for dashboard view."""
    stmt = select(Machine).order_by(Machine.registered_at.desc())
    result = await db.execute(stmt)
    machines = result.scalars().all()

    dashboard_data = []
    for machine in machines:
        tasks_stmt = (
            select(Task)
            .where(
                Task.target_machine_id == machine.id,
                Task.status.in_(["running", "dispatched"])
            )
            .order_by(Task.created_at.desc())
            .limit(5)
        )
        tasks_result = await db.execute(tasks_stmt)
        running_tasks = tasks_result.scalars().all()

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        completed_stmt = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.target_machine_id == machine.id,
                Task.status == "completed",
                Task.completed_at >= today_start
            )
        )
        completed_result = await db.execute(completed_stmt)
        completed_count = completed_result.scalar() or 0

        dashboard_data.append(
            MachineDashboardResponse(
                id=machine.id,
                machine_id=machine.machine_id,
                machine_name=machine.machine_name,
                agent_type=machine.agent_type,
                agent_capability=machine.agent_capability,
                status=machine.status,
                is_enabled=machine.is_enabled,
                agent_status=machine.agent_status,
                last_poll_at=machine.last_poll_at,
                running_tasks=[TaskListResponse.model_validate(t) for t in running_tasks],
                completed_tasks_count=completed_count,
            ).model_dump(mode="json")
        )

    return ApiResponse(data=dashboard_data)


@router.get("/{machine_uuid}", response_model=ApiResponse)
async def get_machine(machine_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get machine details with pending task count."""
    stmt = select(Machine).where(Machine.id == machine_uuid)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    count_stmt = (
        select(func.count())
        .select_from(Task)
        .where(Task.target_machine_id == machine.id, Task.status.in_(["pending", "dispatched", "running"]))
    )
    count_result = await db.execute(count_stmt)
    pending_count = count_result.scalar() or 0

    resp = MachineResponse.model_validate(machine)
    resp.pending_task_count = pending_count

    return ApiResponse(data=resp.model_dump(mode="json"))


@router.patch("/{machine_uuid}", response_model=ApiResponse)
async def update_machine(
    machine_uuid: uuid.UUID,
    payload: MachineUpdateStatus,
    db: AsyncSession = Depends(get_db),
):
    """Update machine status (enable/disable) or online/offline status."""
    stmt = select(Machine).where(Machine.id == machine_uuid)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if payload.is_enabled is not None:
        machine.is_enabled = payload.is_enabled
    if payload.status is not None:
        machine.status = payload.status.value
    if payload.agent_status is not None:
        machine.agent_status = payload.agent_status.value

    await db.flush()

    return ApiResponse(
        data=MachineListResponse.model_validate(machine).model_dump(mode="json"),
        message="Machine updated successfully",
    )


@router.get("/{machine_uuid}/poll", response_model=PollResponse)
async def poll_tasks(
    machine_uuid: uuid.UUID,
    project_id: str | None = Query(default=None, description="已废弃：自动使用机器绑定的项目"),
    db: AsyncSession = Depends(get_db),
):
    """Device polls for pending tasks. Updates heartbeat and returns tasks.
    Returns both pre-assigned tasks and unassigned tasks within machine's own project (auto-claim)."""
    stmt = select(Machine).where(Machine.id == machine_uuid)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    # Update heartbeat
    machine.last_poll_at = datetime.now(timezone.utc)
    machine.status = "online"

    # Pre-assigned pending tasks for this machine
    assigned_stmt = select(Task).where(
        Task.target_machine_id == machine.id,
        Task.status == "pending",
    ).order_by(Task.created_at.asc())
    assigned_result = await db.execute(assigned_stmt)
    assigned_tasks = list(assigned_result.scalars().all())

    # Auto-claim: unassigned pending tasks ONLY within machine's own project
    unassigned_stmt = select(Task).where(
        Task.target_machine_id.is_(None),
        Task.status == "pending",
        Task.project_id == machine.project_id,
    ).order_by(Task.created_at.asc())
    unassigned_result = await db.execute(unassigned_stmt)
    unassigned_tasks = list(unassigned_result.scalars().all())

    poll_tasks_out: list[PollTaskResponse] = []

    # Claim unassigned tasks
    for task in unassigned_tasks:
        task.target_machine_id = machine.id
        task.status = "dispatched"
        poll_tasks_out.append(
            PollTaskResponse(
                id=task.id,
                task_id=task.task_id,
                instruction=task.instruction,
                status="dispatched",
                project_id=task.project_id,
                agent_capability=machine.agent_capability,
            )
        )

    # Pre-assigned tasks
    for task in assigned_tasks:
        task.status = "dispatched"
        poll_tasks_out.append(
            PollTaskResponse(
                id=task.id,
                task_id=task.task_id,
                instruction=task.instruction,
                status="dispatched",
                project_id=task.project_id,
                agent_capability=machine.agent_capability,
            )
        )

    return PollResponse(
        machine=MachineListResponse.model_validate(machine),
        tasks=poll_tasks_out,
    )
