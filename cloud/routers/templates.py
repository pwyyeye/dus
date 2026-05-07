import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import TaskTemplate
from schemas import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    ApiResponse,
)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.post("", response_model=ApiResponse)
async def create_template(payload: TemplateCreate, db: AsyncSession = Depends(get_db)):
    """Create a new task template."""
    template = TaskTemplate(
        name=payload.name,
        description=payload.description,
        instruction=payload.instruction,
        category=payload.category,
    )
    db.add(template)
    await db.flush()

    return ApiResponse(
        data=TemplateResponse.model_validate(template).model_dump(mode="json"),
        message="Template created successfully",
    )


@router.get("", response_model=ApiResponse)
async def list_templates(
    category: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List templates with optional category filter."""
    stmt = select(TaskTemplate)
    if category:
        stmt = stmt.where(TaskTemplate.category == category)
    stmt = stmt.where(TaskTemplate.is_enabled == True).order_by(
        TaskTemplate.created_at.desc()
    ).offset(offset).limit(limit)

    result = await db.execute(stmt)
    templates = result.scalars().all()

    return ApiResponse(
        data=[TemplateResponse.model_validate(t).model_dump(mode="json") for t in templates]
    )


@router.get("/{template_uuid}", response_model=ApiResponse)
async def get_template(template_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get template details."""
    stmt = select(TaskTemplate).where(TaskTemplate.id == template_uuid)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return ApiResponse(data=TemplateResponse.model_validate(template).model_dump(mode="json"))


@router.put("/{template_uuid}", response_model=ApiResponse)
async def update_template(
    template_uuid: uuid.UUID, payload: TemplateUpdate, db: AsyncSession = Depends(get_db)
):
    """Update template settings."""
    stmt = select(TaskTemplate).where(TaskTemplate.id == template_uuid)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.instruction is not None:
        template.instruction = payload.instruction
    if payload.category is not None:
        template.category = payload.category
    if payload.is_enabled is not None:
        template.is_enabled = payload.is_enabled

    return ApiResponse(
        data=TemplateResponse.model_validate(template).model_dump(mode="json"),
        message="Template updated successfully",
    )


@router.delete("/{template_uuid}", response_model=ApiResponse)
async def delete_template(template_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Soft-delete a template (disable it)."""
    stmt = select(TaskTemplate).where(TaskTemplate.id == template_uuid)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_enabled = False

    return ApiResponse(message="Template deleted successfully")
