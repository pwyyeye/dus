import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Label, Issue, IssueLabel
from schemas import LabelCreate, LabelResponse, ApiResponse

router = APIRouter(prefix="/labels", tags=["labels"])


@router.post("", response_model=ApiResponse)
async def create_label(payload: LabelCreate, db: AsyncSession = Depends(get_db)):
    """Create a new label."""
    dup_stmt = select(Label).where(Label.name == payload.name)
    dup_result = await db.execute(dup_stmt)
    if dup_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Label with this name already exists")

    label = Label(name=payload.name, color=payload.color)
    db.add(label)
    await db.flush()

    return ApiResponse(
        data=LabelResponse.model_validate(label).model_dump(mode="json"),
        message="Label created",
    )


@router.get("", response_model=ApiResponse)
async def list_labels(db: AsyncSession = Depends(get_db)):
    """List all labels."""
    stmt = select(Label).order_by(Label.name)
    result = await db.execute(stmt)
    labels = result.scalars().all()

    return ApiResponse(
        data=[LabelResponse.model_validate(l).model_dump(mode="json") for l in labels]
    )


@router.put("/{label_id}", response_model=ApiResponse)
async def update_label(
    label_id: uuid.UUID,
    payload: LabelCreate,
    db: AsyncSession = Depends(get_db),
):
    """Update a label."""
    stmt = select(Label).where(Label.id == label_id)
    result = await db.execute(stmt)
    label = result.scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    if payload.name is not None and payload.name != label.name:
        dup_stmt = select(Label).where(Label.name == payload.name)
        dup_result = await db.execute(dup_stmt)
        if dup_result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Label with this name already exists")
        label.name = payload.name
    if payload.color is not None:
        label.color = payload.color

    await db.flush()
    return ApiResponse(
        data=LabelResponse.model_validate(label).model_dump(mode="json"),
        message="Label updated",
    )


@router.delete("/{label_id}", response_model=ApiResponse)
async def delete_label(label_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a label. Removes associations with issues automatically."""
    stmt = select(Label).where(Label.id == label_id)
    result = await db.execute(stmt)
    label = result.scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    await db.delete(label)
    await db.flush()
    return ApiResponse(message="Label deleted")


# Issue-Label association endpoints


@router.post("/issues/{issue_uuid}/labels/{label_id}", response_model=ApiResponse)
async def add_label_to_issue(
    issue_uuid: uuid.UUID,
    label_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Attach a label to an issue."""
    issue_stmt = select(Issue).where(Issue.id == issue_uuid)
    issue_result = await db.execute(issue_stmt)
    issue = issue_result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    label_stmt = select(Label).where(Label.id == label_id)
    label_result = await db.execute(label_stmt)
    label = label_result.scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    if label not in issue.labels:
        issue.labels.append(label)
        await db.flush()

    return ApiResponse(message="Label attached to issue")


@router.delete("/issues/{issue_uuid}/labels/{label_id}", response_model=ApiResponse)
async def remove_label_from_issue(
    issue_uuid: uuid.UUID,
    label_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Detach a label from an issue."""
    issue_stmt = select(Issue).where(Issue.id == issue_uuid)
    issue_result = await db.execute(issue_stmt)
    issue = issue_result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    label_stmt = select(Label).where(Label.id == label_id)
    label_result = await db.execute(label_stmt)
    label = label_result.scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    if label in issue.labels:
        issue.labels.remove(label)
        await db.flush()

    return ApiResponse(message="Label detached from issue")
