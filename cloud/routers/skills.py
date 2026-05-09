import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Skill, Agent
from schemas import SkillCreate, SkillResponse, ApiResponse

router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("", response_model=ApiResponse)
async def create_skill(payload: SkillCreate, db: AsyncSession = Depends(get_db)):
    """Create a new skill."""
    dup_stmt = select(Skill).where(Skill.name == payload.name)
    dup_result = await db.execute(dup_stmt)
    if dup_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Skill with this name already exists")

    skill = Skill(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        config=payload.config,
    )
    db.add(skill)
    await db.flush()

    return ApiResponse(
        data=SkillResponse.model_validate(skill).model_dump(mode="json"),
        message="Skill created",
    )


@router.get("", response_model=ApiResponse)
async def list_skills(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all skills with optional category filter."""
    stmt = select(Skill)
    if category:
        stmt = stmt.where(Skill.category == category)
    stmt = stmt.order_by(Skill.name)

    result = await db.execute(stmt)
    skills = result.scalars().all()

    return ApiResponse(
        data=[SkillResponse.model_validate(s).model_dump(mode="json") for s in skills]
    )


@router.get("/{skill_id}", response_model=ApiResponse)
async def get_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get skill details."""
    stmt = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return ApiResponse(
        data=SkillResponse.model_validate(skill).model_dump(mode="json")
    )


@router.put("/{skill_id}", response_model=ApiResponse)
async def update_skill(
    skill_id: uuid.UUID,
    payload: SkillCreate,
    db: AsyncSession = Depends(get_db),
):
    """Update a skill."""
    stmt = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if payload.name is not None and payload.name != skill.name:
        dup_stmt = select(Skill).where(Skill.name == payload.name)
        dup_result = await db.execute(dup_stmt)
        if dup_result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Skill with this name already exists")
        skill.name = payload.name
    if payload.description is not None:
        skill.description = payload.description
    if payload.category is not None:
        skill.category = payload.category
    if payload.config is not None:
        skill.config = payload.config

    await db.flush()

    return ApiResponse(
        data=SkillResponse.model_validate(skill).model_dump(mode="json"),
        message="Skill updated",
    )


@router.delete("/{skill_id}", response_model=ApiResponse)
async def delete_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a skill. Removes agent associations automatically."""
    stmt = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    await db.delete(skill)
    await db.flush()
    return ApiResponse(message="Skill deleted")
