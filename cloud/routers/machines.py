import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Machine, Task, Project, Agent, ApiBan, Issue
from schemas import (
    MachineCreate,
    MachineResponse,
    MachineListResponse,
    MachineRegisterResponse,
    MachineStatus,
    AgentStatus,
    AgentType,
    ApiResponse,
    PollResponse,
    PollTaskResponse,
    AgentConfig,
    MachineUpdateStatus,
    MachineDashboardResponse,
    TaskListResponse,
    ApiBanCreate,
    ApiBanResponse,
)
from connection_manager import manager as ws_manager

router = APIRouter(prefix="/machines", tags=["machines"])
# Public router: endpoints that don't require API key auth
public_router = APIRouter(prefix="/machines", tags=["machines"])



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
                root_path=payload.project_root,
            )
            db.add(project)
            await db.flush()
        elif payload.project_root and not project.root_path:
            # Update existing project's root_path if not set
            project.root_path = payload.project_root
        resolved_project_id = project.id

    stmt = select(Machine).where(Machine.machine_id == payload.machine_id)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()

    if machine:
        machine.machine_name = payload.machine_name
        machine.agent_type = payload.agent_type.value
        machine.agent_capability = payload.agent_capability.value
        machine.agent_version = payload.agent_version
        if payload.available_agents is not None:
            machine.available_agents = payload.available_agents
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
            available_agents=payload.available_agents or [],
            status="online",
            project_id=resolved_project_id,
            last_poll_at=datetime.now(timezone.utc),
        )
        db.add(machine)

    await db.flush()

    try:
        await ws_manager.broadcast(
            "machine.updated",
            {"id": str(machine.id), "status": machine.status, "machine_id": machine.machine_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=MachineListResponse.model_validate(machine).model_dump(mode="json"),
        message="Machine registered successfully",
    )


@public_router.post("/register", response_model=ApiResponse)
async def register_machine_with_key(
    payload: MachineCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new machine and auto-generate an API key.

    This endpoint does NOT require authentication. The server generates a
    random API key, stores it on the Machine record along with the client IP,
    and returns it to the bridge for persistent use.
    """
    client_ip = request.client.host if request.client else None

    # Auto-create project if needed
    resolved_project_id = None
    if payload.project_id:
        stmt = select(Project).where(Project.project_id == payload.project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            project = Project(
                project_id=payload.project_id,
                project_name=payload.project_id,
                root_path=payload.project_root,
            )
            db.add(project)
            await db.flush()
        elif payload.project_root and not project.root_path:
            project.root_path = payload.project_root
        resolved_project_id = project.id

    stmt = select(Machine).where(Machine.machine_id == payload.machine_id)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()

    api_key = secrets.token_hex(32)

    if machine:
        machine.machine_name = payload.machine_name
        machine.agent_type = payload.agent_type.value
        machine.agent_capability = payload.agent_capability.value
        machine.agent_version = payload.agent_version
        if payload.available_agents is not None:
            machine.available_agents = payload.available_agents
        machine.status = "online"
        machine.project_id = resolved_project_id or machine.project_id
        machine.last_poll_at = datetime.now(timezone.utc)
        machine.api_key = api_key
        machine.ip_address = client_ip
    else:
        machine = Machine(
            machine_id=payload.machine_id,
            machine_name=payload.machine_name,
            agent_type=payload.agent_type.value,
            agent_capability=payload.agent_capability.value,
            agent_version=payload.agent_version,
            available_agents=payload.available_agents or [],
            status="online",
            project_id=resolved_project_id,
            last_poll_at=datetime.now(timezone.utc),
            api_key=api_key,
            ip_address=client_ip,
        )
        db.add(machine)

    await db.flush()

    try:
        await ws_manager.broadcast(
            "machine.updated",
            {"id": str(machine.id), "status": machine.status, "machine_id": machine.machine_id},
        )
    except Exception:
        pass

    return ApiResponse(
        data=MachineRegisterResponse.model_validate(machine).model_dump(mode="json"),
        message="Machine registered successfully",
    )


@router.post("/ban", response_model=ApiResponse)
async def ban_target(
    payload: ApiBanCreate,
    db: AsyncSession = Depends(get_db),
):
    """Ban an IP address or API key."""
    # Check if already banned
    stmt = select(ApiBan).where(
        ApiBan.target_type == payload.target_type,
        ApiBan.target_value == payload.target_value,
        ApiBan.is_active == True,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return ApiResponse(message="Already banned", data=ApiBanResponse.model_validate(existing).model_dump(mode="json"))

    ban = ApiBan(
        target_type=payload.target_type,
        target_value=payload.target_value,
        reason=payload.reason,
    )
    db.add(ban)
    await db.flush()

    return ApiResponse(
        data=ApiBanResponse.model_validate(ban).model_dump(mode="json"),
        message="Ban created successfully",
    )


@router.delete("/ban/{ban_id}", response_model=ApiResponse)
async def unban_target(
    ban_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a ban (unban)."""
    stmt = select(ApiBan).where(ApiBan.id == ban_id)
    result = await db.execute(stmt)
    ban = result.scalar_one_or_none()
    if not ban:
        raise HTTPException(status_code=404, detail="Ban not found")

    ban.is_active = False
    await db.flush()

    return ApiResponse(message="Ban removed successfully")


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
    if payload.agent_version is not None:
        machine.agent_version = payload.agent_version

    await db.flush()

    try:
        await ws_manager.broadcast(
            "machine.updated",
            {"id": str(machine.id), "status": machine.status, "machine_id": machine.machine_id, "agent_status": machine.agent_status},
        )
    except Exception:
        pass

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

    # Auto-claim: unassigned pending tasks
    # 条件1: 同一项目的任务
    # 条件2: Issue 处于 in_progress 且无 assignee（可被任意 agent 认领）
    unassigned_stmt = (
        select(Task)
        .join(Issue, Task.issue_id == Issue.id, isouter=True)
        .where(
            Task.target_machine_id.is_(None),
            Task.status == "pending",
            or_(
                Task.project_id == machine.project_id,
                and_(
                    Task.issue_id.isnot(None),
                    Issue.status == "in_progress",
                    Issue.assignee_id.is_(None),
                ),
            ),
        )
        .order_by(Task.created_at.asc())
    )
    unassigned_result = await db.execute(unassigned_stmt)
    unassigned_tasks = list(unassigned_result.scalars().all())

    poll_tasks_out: list[PollTaskResponse] = []

    # Helper: resolve prior session for issue-bound tasks
    async def resolve_prior_session(issue_id: uuid.UUID | None) -> tuple[str | None, str | None]:
        if not issue_id:
            return None, None
        from sqlalchemy import select as sa_select
        prior_stmt = (
            sa_select(Task)
            .where(
                Task.issue_id == issue_id,
                Task.status.in_(["completed", "failed"]),
                Task.session_id.is_not(None),
            )
            .order_by(Task.completed_at.desc())
            .limit(1)
        )
        prior_result = await db.execute(prior_stmt)
        prior_task = prior_result.scalar_one_or_none()
        if prior_task:
            return prior_task.session_id, prior_task.work_dir
        return None, None

    # Helper: resolve agent config from issue's agent assignee
    async def resolve_agent_config(issue_id: uuid.UUID | None) -> AgentConfig | None:
        if not issue_id:
            return None
        from models import Issue as IssueModel
        issue_stmt = select(IssueModel).where(IssueModel.id == issue_id)
        issue_result = await db.execute(issue_stmt)
        issue_obj = issue_result.scalar_one_or_none()
        if not issue_obj or issue_obj.assignee_type != "agent" or not issue_obj.assignee_id:
            return None
        agent_stmt = select(Agent).where(
            Agent.id == issue_obj.assignee_id,
            Agent.is_enabled == True,
        )
        agent_result = await db.execute(agent_stmt)
        agent_obj = agent_result.scalar_one_or_none()
        if not agent_obj:
            return None
        return AgentConfig(
            agent_id=str(agent_obj.id),
            name=agent_obj.name,
            instructions=agent_obj.instructions,
            model=agent_obj.model,
            custom_env=agent_obj.custom_env,
            custom_args=agent_obj.custom_args,
            mcp_config=agent_obj.mcp_config,
        )

    # Claim unassigned tasks (atomic to prevent concurrent claim)
    from sqlalchemy import update
    for task in unassigned_tasks:
        # Atomic claim: only update if still pending and unassigned
        claim_stmt = (
            update(Task)
            .where(
                Task.id == task.id,
                Task.target_machine_id.is_(None),
                Task.status == "pending"
            )
            .values(target_machine_id=machine.id, status="dispatched")
        )
        result = await db.execute(claim_stmt)
        if result.rowcount == 1:
            # Successfully claimed
            prior_session, prior_workdir = await resolve_prior_session(task.issue_id)
            agent_config = await resolve_agent_config(task.issue_id)
            poll_tasks_out.append(
                PollTaskResponse(
                    id=task.id,
                    task_id=task.task_id,
                    instruction=task.instruction,
                    status="dispatched",
                    project_id=task.project_id,
                    agent_capability=machine.agent_capability,
                    agent_cli_id=task.agent_cli_id,
                    issue_id=task.issue_id,
                    prior_session_id=prior_session,
                    prior_work_dir=prior_workdir,
                    agent_config=agent_config,
                )
            )

    # Pre-assigned tasks
    for task in assigned_tasks:
        task.status = "dispatched"
        prior_session, prior_workdir = await resolve_prior_session(task.issue_id)
        agent_config = await resolve_agent_config(task.issue_id)
        poll_tasks_out.append(
            PollTaskResponse(
                id=task.id,
                task_id=task.task_id,
                instruction=task.instruction,
                status="dispatched",
                project_id=task.project_id,
                agent_capability=machine.agent_capability,
                agent_cli_id=task.agent_cli_id,
                issue_id=task.issue_id,
                prior_session_id=prior_session,
                prior_work_dir=prior_workdir,
                agent_config=agent_config,
            )
        )

    # Broadcast task status changes caused by poll
    for pt in poll_tasks_out:
        try:
            await ws_manager.broadcast(
                "task.updated",
                {"id": str(pt.id), "status": pt.status, "task_id": pt.task_id},
            )
        except Exception:
            pass

    return PollResponse(
        machine=MachineListResponse.model_validate(machine),
        tasks=poll_tasks_out,
    )
