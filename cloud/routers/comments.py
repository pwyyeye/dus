import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database import get_db
from models import Comment, Issue, Task, Agent, Machine, ChatSession
from schemas import CommentCreate, CommentUpdate, CommentResponse, ApiResponse
from util.mention import parse_mentions, has_mention_all

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comments", tags=["comments"])


async def _create_task_for_issue(
    issue: Issue,
    instruction: str,
    db: AsyncSession,
    mentioned_agent_id: uuid.UUID | None = None,
) -> Task | None:
    """Create a Task for an issue, reusing existing active ChatSession if available."""
    target_machine_id = None

    if mentioned_agent_id:
        # Explicit @mention: resolve mentioned agent to machine
        stmt = select(Agent).where(Agent.id == mentioned_agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()
        if not agent or not agent.is_enabled:
            logger.warning(f"Mentioned agent {mentioned_agent_id} not found or disabled, skipping task")
            return None
        target_machine_id = agent.machine_id
    elif issue.assignee_type == "machine" and issue.assignee_id:
        target_machine_id = issue.assignee_id
    elif issue.assignee_type == "agent" and issue.assignee_id:
        stmt = select(Agent).where(Agent.id == issue.assignee_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()
        if not agent or not agent.is_enabled:
            return None
        target_machine_id = agent.machine_id
    else:
        # No assignee, skip
        return None

    # Reuse existing active ChatSession or create a new one
    existing_session = next(
        (s for s in issue.chat_sessions if s.status == "active"), None
    )
    chat_session = existing_session if existing_session else ChatSession(issue_id=issue.id, status="active")
    if not existing_session:
        db.add(chat_session)
        await db.flush()

    task = Task(
        task_id=f"task-{uuid.uuid4().hex[:8]}",
        instruction=instruction,
        project_id=issue.project_id,
        target_machine_id=target_machine_id,
        issue_id=issue.id,
        agent_cli_id=issue.agent_cli_id,
        chat_session_id=chat_session.id,
        status="pending",
    )
    db.add(task)
    await db.flush()
    return task


@router.post("", response_model=ApiResponse)
async def create_comment(payload: CommentCreate, db: AsyncSession = Depends(get_db)):
    """Create a comment on an issue.

    Auto-triggers a Task when:
    - The issue has an active assignee (machine or agent), OR
    - The comment content contains an @mention of a specific agent
    """
    # Load issue with chat_sessions for task creation
    issue_stmt = select(Issue).options(
        joinedload(Issue.chat_sessions),
        joinedload(Issue.tasks),
    ).where(Issue.id == payload.issue_id)
    issue_result = await db.execute(issue_stmt)
    issue = issue_result.unique().scalar_one_or_none()
    if not issue:
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

    # ── Auto-task trigger ──
    if issue.status not in ("done", "cancelled"):
        mentioned_agents = parse_mentions(payload.content)
        mention_all = has_mention_all(payload.content)

        # on_mention: explicitly mentioned agents
        for _, agent_id in mentioned_agents:
            await _create_task_for_issue(issue, payload.content, db, mentioned_agent_id=agent_id)
            logger.info(f"Task created for mentioned agent {agent_id} on issue {issue.issue_id}")

        # on_comment: issue has assignee, no @all, not a reply, no explicit mentions
        # → trigger assignee
        if (
            not mention_all
            and not mentioned_agents
            and not payload.parent_id
            and issue.assignee_id
            and issue.status == "in_progress"
        ):
            # Only create if no pending/dispatched task already exists
            has_pending = any(
                t.status in ("pending", "dispatched") for t in issue.tasks
            )
            if not has_pending:
                task = await _create_task_for_issue(issue, payload.content, db)
                if task:
                    logger.info(f"Task {task.task_id} auto-created for comment on issue {issue.issue_id}")

    return ApiResponse(
        data=CommentResponse(
            id=comment.id,
            issue_id=comment.issue_id,
            parent_id=comment.parent_id,
            content=comment.content,
            author_name=comment.author_name,
            created_at=comment.created_at,
            replies=[],
        ).model_dump(mode="json"),
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
