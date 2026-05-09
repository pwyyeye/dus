import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db
from models import Agent, Machine, Skill, Task
from schemas import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    SkillResponse,
    ApiResponse,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        machine_id=agent.machine_id,
        instructions=agent.instructions,
        model=agent.model,
        custom_env=agent.custom_env,
        custom_args=agent.custom_args,
        mcp_config=agent.mcp_config,
        max_concurrent_tasks=agent.max_concurrent_tasks,
        is_enabled=agent.is_enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        machine=agent.machine,
        skills=[SkillResponse.model_validate(s) for s in agent.skills],
    )


@router.post("", response_model=ApiResponse)
async def create_agent(payload: AgentCreate, db: AsyncSession = Depends(get_db)):
    """Create a new agent bound to a machine."""
    stmt = select(Machine).where(Machine.id == payload.machine_id)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=400, detail="Machine not found")

    agent = Agent(
        name=payload.name,
        description=payload.description,
        machine_id=payload.machine_id,
        instructions=payload.instructions,
        model=payload.model,
        custom_env=payload.custom_env,
        custom_args=payload.custom_args,
        mcp_config=payload.mcp_config,
        max_concurrent_tasks=payload.max_concurrent_tasks,
    )
    db.add(agent)
    await db.flush()

    # Attach skills
    if payload.skill_ids:
        skill_stmt = select(Skill).where(Skill.id.in_(payload.skill_ids))
        skill_result = await db.execute(skill_stmt)
        agent.skills = list(skill_result.scalars().all())

    stmt = select(Agent).where(Agent.id == agent.id).options(
        joinedload(Agent.machine),
        joinedload(Agent.skills),
    )
    result = await db.execute(stmt)
    agent = result.unique().scalar_one()

    return ApiResponse(
        data=_agent_to_response(agent).model_dump(mode="json"),
        message="Agent created successfully",
    )


@router.get("", response_model=ApiResponse)
async def list_agents(
    machine_id: uuid.UUID | None = None,
    is_enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all agents with optional filters."""
    stmt = select(Agent).options(
        joinedload(Agent.machine),
        joinedload(Agent.skills),
    )
    if machine_id:
        stmt = stmt.where(Agent.machine_id == machine_id)
    if is_enabled is not None:
        stmt = stmt.where(Agent.is_enabled == is_enabled)
    stmt = stmt.order_by(Agent.created_at.desc())

    result = await db.execute(stmt)
    agents = result.unique().scalars().all()

    return ApiResponse(
        data=[
            AgentListResponse(
                id=a.id,
                name=a.name,
                description=a.description,
                machine_id=a.machine_id,
                model=a.model,
                max_concurrent_tasks=a.max_concurrent_tasks,
                is_enabled=a.is_enabled,
                created_at=a.created_at,
                updated_at=a.updated_at,
                machine=a.machine,
                skills=[SkillResponse.model_validate(s) for s in a.skills],
            ).model_dump(mode="json")
            for a in agents
        ]
    )


@router.get("/{agent_uuid}", response_model=ApiResponse)
async def get_agent(agent_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get agent details."""
    stmt = select(Agent).where(Agent.id == agent_uuid).options(
        joinedload(Agent.machine),
        joinedload(Agent.skills),
    )
    result = await db.execute(stmt)
    agent = result.unique().scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return ApiResponse(data=_agent_to_response(agent).model_dump(mode="json"))


@router.patch("/{agent_uuid}", response_model=ApiResponse)
async def update_agent(
    agent_uuid: uuid.UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update agent configuration."""
    stmt = select(Agent).where(Agent.id == agent_uuid).options(
        joinedload(Agent.machine),
        joinedload(Agent.skills),
    )
    result = await db.execute(stmt)
    agent = result.unique().scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.machine_id is not None:
        machine_stmt = select(Machine).where(Machine.id == payload.machine_id)
        machine_result = await db.execute(machine_stmt)
        if not machine_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Machine not found")
        agent.machine_id = payload.machine_id

    for field in ("name", "description", "instructions", "model", "custom_env",
                  "custom_args", "mcp_config", "max_concurrent_tasks", "is_enabled"):
        val = getattr(payload, field, None)
        if val is not None:
            setattr(agent, field, val)

    # Update skills
    if payload.skill_ids is not None:
        if payload.skill_ids:
            skill_stmt = select(Skill).where(Skill.id.in_(payload.skill_ids))
            skill_result = await db.execute(skill_stmt)
            agent.skills = list(skill_result.scalars().all())
        else:
            agent.skills = []

    agent.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return ApiResponse(
        data=_agent_to_response(agent).model_dump(mode="json"),
        message="Agent updated successfully",
    )


@router.delete("/{agent_uuid}", response_model=ApiResponse)
async def delete_agent(agent_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete an agent."""
    stmt = select(Agent).where(Agent.id == agent_uuid)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.flush()

    return ApiResponse(message="Agent deleted successfully")


@router.get("/{agent_uuid}/activity", response_model=ApiResponse)
async def get_agent_activity(
    agent_uuid: uuid.UUID,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Get agent activity statistics for the last N days (for sparkline chart)."""
    stmt = select(Agent).where(Agent.id == agent_uuid)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get tasks assigned to this agent's machine in the last N days
    since = datetime.now(timezone.utc) - timedelta(days=days)
    tasks_stmt = (
        select(
            cast(Task.created_at, Date).label("date"),
            func.count().label("count"),
        )
        .where(
            Task.target_machine_id == agent.machine_id,
            Task.created_at >= since,
        )
        .group_by(cast(Task.created_at, Date))
        .order_by(cast(Task.created_at, Date))
    )
    tasks_result = await db.execute(tasks_stmt)
    rows = tasks_result.all()

    # Build complete date range with zeros for missing days
    activity = []
    current = since.date()
    end = datetime.now(timezone.utc).date()
    row_map = {str(r.date): r.count for r in rows}

    while current <= end:
        activity.append({
            "date": str(current),
            "count": row_map.get(str(current), 0),
        })
        current += timedelta(days=1)

    return ApiResponse(data=activity)
