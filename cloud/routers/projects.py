import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Project
from schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ApiResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _generate_project_id() -> str:
    return f"proj-{uuid.uuid4().hex[:8]}"


@router.post("", response_model=ApiResponse)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new project."""
    project = Project(
        project_id=_generate_project_id(),
        project_name=payload.project_name,
        root_path=payload.root_path,
        idle_threshold_hours=payload.idle_threshold_hours,
        reminder_interval_hours=payload.reminder_interval_hours,
        last_activity_at=datetime.now(timezone.utc),
    )
    db.add(project)
    await db.flush()

    resp = ProjectResponse.model_validate(project)
    resp.idle_hours = 0.0

    return ApiResponse(
        data=resp.model_dump(mode="json"),
        message="Project created successfully",
    )


@router.get("", response_model=ApiResponse)
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects with idle hours calculation."""
    stmt = select(Project).where(Project.is_archived == False).order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    projects = result.scalars().all()

    now = datetime.now(timezone.utc)
    data = []
    for p in projects:
        resp = ProjectResponse.model_validate(p)
        if p.last_activity_at:
            delta = now - p.last_activity_at.replace(tzinfo=timezone.utc) if p.last_activity_at.tzinfo is None else now - p.last_activity_at
            resp.idle_hours = round(delta.total_seconds() / 3600, 1)
        else:
            resp.idle_hours = None
        data.append(resp.model_dump(mode="json"))

    return ApiResponse(data=data)


@router.put("/{project_uuid}", response_model=ApiResponse)
async def update_project(
    project_uuid: uuid.UUID, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    """Update project settings."""
    stmt = select(Project).where(Project.id == project_uuid)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.project_name is not None:
        project.project_name = payload.project_name
    if payload.root_path is not None:
        project.root_path = payload.root_path
    if payload.idle_threshold_hours is not None:
        project.idle_threshold_hours = payload.idle_threshold_hours
    if payload.reminder_interval_hours is not None:
        project.reminder_interval_hours = payload.reminder_interval_hours
    if payload.is_archived is not None:
        project.is_archived = payload.is_archived

    resp = ProjectResponse.model_validate(project)

    return ApiResponse(
        data=resp.model_dump(mode="json"),
        message="Project updated successfully",
    )
