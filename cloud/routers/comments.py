import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Comment, Issue
from schemas import CommentCreate, CommentUpdate, CommentResponse, ApiResponse

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("", response_model=ApiResponse)
async def create_comment(payload: CommentCreate, db: AsyncSession = Depends(get_db)):
    """Create a comment on an issue. Supports nested replies."""
    issue_stmt = select(Issue).where(Issue.id == payload.issue_id)
    issue_result = await db.execute(issue_stmt)
    if not issue_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Issue not found")

    if payload.parent_id:
        parent_stmt = select(Comment).where(Comment.id == payload.parent_id)
        parent_result = await db.execute(parent_stmt)
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")
        if parent.issue_id != payload.issue_id:
            raise HTTPException(status_code=400, detail="Parent comment belongs to a different issue")

    comment = Comment(
        issue_id=payload.issue_id,
        parent_id=payload.parent_id,
        content=payload.content,
        author_name=payload.author_name,
    )
    db.add(comment)
    await db.flush()

    return ApiResponse(
        data=CommentResponse.model_validate(comment).model_dump(mode="json"),
        message="Comment created",
    )


@router.get("/issue/{issue_uuid}", response_model=ApiResponse)
async def list_issue_comments(
    issue_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all comments for an issue, structured as a tree."""
    issue_stmt = select(Issue).where(Issue.id == issue_uuid)
    issue_result = await db.execute(issue_stmt)
    if not issue_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Issue not found")

    stmt = select(Comment).where(Comment.issue_id == issue_uuid)
    result = await db.execute(stmt)
    comments = result.scalars().all()

    comment_map = {c.id: CommentResponse.model_validate(c) for c in comments}
    root_comments = []
    for c in comments:
        cr = comment_map[c.id]
        if c.parent_id and c.parent_id in comment_map:
            comment_map[c.parent_id].replies.append(cr)
        else:
            root_comments.append(cr)

    root_comments.sort(key=lambda x: x.created_at)
    return ApiResponse(data=[c.model_dump(mode="json") for c in root_comments])


@router.put("/{comment_id}", response_model=ApiResponse)
async def update_comment(
    comment_id: uuid.UUID,
    payload: CommentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a comment."""
    stmt = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if payload.content is not None:
        comment.content = payload.content

    await db.flush()
    return ApiResponse(
        data=CommentResponse.model_validate(comment).model_dump(mode="json"),
        message="Comment updated",
    )


@router.delete("/{comment_id}", response_model=ApiResponse)
async def delete_comment(comment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a comment and all its replies."""
    stmt = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    await db.delete(comment)
    await db.flush()
    return ApiResponse(message="Comment deleted")
