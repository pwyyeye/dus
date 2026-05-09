import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import InboxItem
from schemas import InboxItemCreate, InboxItemResponse, ApiResponse
from connection_manager import manager as ws_manager

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.post("", response_model=ApiResponse)
async def create_inbox_item(payload: InboxItemCreate, db: AsyncSession = Depends(get_db)):
    """Create an inbox item (notification)."""
    item = InboxItem(
        title=payload.title,
        message=payload.message,
        item_type=payload.item_type,
        source_type=payload.source_type,
        source_id=payload.source_id,
    )
    db.add(item)
    await db.flush()

    try:
        await ws_manager.broadcast(
            "inbox.new",
            {"id": str(item.id), "title": item.title, "item_type": item.item_type},
        )
    except Exception:
        pass

    return ApiResponse(
        data=InboxItemResponse.model_validate(item).model_dump(mode="json"),
        message="Inbox item created",
    )


@router.get("", response_model=ApiResponse)
async def list_inbox_items(
    is_read: bool | None = None,
    item_type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List inbox items with optional filters."""
    stmt = select(InboxItem)
    if is_read is not None:
        stmt = stmt.where(InboxItem.is_read == is_read)
    if item_type:
        stmt = stmt.where(InboxItem.item_type == item_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = stmt.order_by(InboxItem.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return ApiResponse(
        data=[InboxItemResponse.model_validate(i).model_dump(mode="json") for i in items],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@router.get("/unread-count", response_model=ApiResponse)
async def get_unread_count(db: AsyncSession = Depends(get_db)):
    """Get count of unread inbox items."""
    stmt = select(func.count()).where(InboxItem.is_read == False)
    result = await db.execute(stmt)
    count = result.scalar() or 0

    return ApiResponse(data={"count": count})


@router.put("/{item_id}/read", response_model=ApiResponse)
async def mark_read(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Mark an inbox item as read."""
    stmt = select(InboxItem).where(InboxItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    item.is_read = True
    await db.flush()

    return ApiResponse(message="Marked as read")


@router.post("/read-all", response_model=ApiResponse)
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    """Mark all inbox items as read."""
    stmt = update(InboxItem).where(InboxItem.is_read == False).values(is_read=True)
    await db.execute(stmt)
    await db.flush()

    return ApiResponse(message="All items marked as read")


@router.delete("/{item_id}", response_model=ApiResponse)
async def delete_inbox_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete an inbox item."""
    stmt = select(InboxItem).where(InboxItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    await db.delete(item)
    await db.flush()
    return ApiResponse(message="Inbox item deleted")
