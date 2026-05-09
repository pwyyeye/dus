from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Task, Issue, Machine, Agent, Project, TaskLog
from schemas import ApiResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=ApiResponse)
async def get_overview(db: AsyncSession = Depends(get_db)):
    """Get system-wide overview statistics."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # Counts
    task_total = (await db.execute(select(func.count()).select_from(Task))).scalar() or 0
    issue_total = (await db.execute(select(func.count()).select_from(Issue))).scalar() or 0
    machine_total = (await db.execute(select(func.count()).select_from(Machine))).scalar() or 0
    agent_total = (await db.execute(select(func.count()).select_from(Agent))).scalar() or 0
    project_total = (await db.execute(select(func.count()).select_from(Project))).scalar() or 0

    # Recent activity
    tasks_7d = (await db.execute(
        select(func.count()).select_from(Task).where(Task.created_at >= seven_days_ago)
    )).scalar() or 0
    issues_7d = (await db.execute(
        select(func.count()).select_from(Issue).where(Issue.created_at >= seven_days_ago)
    )).scalar() or 0

    # Task success rate (completed vs failed)
    completed = (await db.execute(
        select(func.count()).select_from(Task).where(Task.status == "completed")
    )).scalar() or 0
    failed = (await db.execute(
        select(func.count()).select_from(Task).where(Task.status == "failed")
    )).scalar() or 0
    success_rate = round(completed / (completed + failed) * 100, 1) if (completed + failed) > 0 else 0

    # Online machines
    online_machines = (await db.execute(
        select(func.count()).select_from(Machine).where(Machine.status == "online")
    )).scalar() or 0

    return ApiResponse(data={
        "counts": {
            "tasks": task_total,
            "issues": issue_total,
            "machines": machine_total,
            "agents": agent_total,
            "projects": project_total,
        },
        "recent": {
            "tasks_7d": tasks_7d,
            "issues_7d": issues_7d,
        },
        "task_success_rate": success_rate,
        "online_machines": online_machines,
    })


@router.get("/tasks", response_model=ApiResponse)
async def get_task_stats(db: AsyncSession = Depends(get_db)):
    """Get task statistics: status distribution and daily trend."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Status distribution
    status_rows = (await db.execute(
        select(Task.status, func.count()).group_by(Task.status)
    )).all()
    status_dist = {row[0]: row[1] for row in status_rows}

    # Daily creation trend (last 30 days)
    daily_rows = (await db.execute(
        select(
            func.date(Task.created_at).label("day"),
            func.count().label("count"),
        )
        .where(Task.created_at >= thirty_days_ago)
        .group_by(func.date(Task.created_at))
        .order_by(func.date(Task.created_at))
    )).all()

    # Fill missing days
    daily_trend = []
    current = thirty_days_ago.date()
    end = now.date()
    row_map = {str(r[0]): r[1] for r in daily_rows}
    while current <= end:
        key = current.isoformat()
        daily_trend.append({"date": key, "count": row_map.get(key, 0)})
        current += timedelta(days=1)

    # Top machines by task count
    machine_rows = (await db.execute(
        select(Machine.machine_name, func.count(Task.id).label("count"))
        .join(Task, Task.target_machine_id == Machine.id)
        .group_by(Machine.machine_name)
        .order_by(func.count(Task.id).desc())
        .limit(10)
    )).all()
    top_machines = [{"name": r[0], "count": r[1]} for r in machine_rows]

    return ApiResponse(data={
        "status_distribution": status_dist,
        "daily_trend": daily_trend,
        "top_machines": top_machines,
    })


@router.get("/issues", response_model=ApiResponse)
async def get_issue_stats(db: AsyncSession = Depends(get_db)):
    """Get issue statistics: status and priority distribution."""
    # Status distribution
    status_rows = (await db.execute(
        select(Issue.status, func.count()).group_by(Issue.status)
    )).all()
    status_dist = {row[0]: row[1] for row in status_rows}

    # Priority distribution
    priority_rows = (await db.execute(
        select(Issue.priority, func.count()).group_by(Issue.priority)
    )).all()
    priority_dist = {row[0]: row[1] for row in priority_rows}

    # Daily creation trend (last 30 days)
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    daily_rows = (await db.execute(
        select(
            func.date(Issue.created_at).label("day"),
            func.count().label("count"),
        )
        .where(Issue.created_at >= thirty_days_ago)
        .group_by(func.date(Issue.created_at))
        .order_by(func.date(Issue.created_at))
    )).all()

    daily_trend = []
    current = thirty_days_ago.date()
    end = now.date()
    row_map = {str(r[0]): r[1] for r in daily_rows}
    while current <= end:
        key = current.isoformat()
        daily_trend.append({"date": key, "count": row_map.get(key, 0)})
        current += timedelta(days=1)

    # Top projects by issue count
    project_rows = (await db.execute(
        select(Project.project_name, func.count(Issue.id).label("count"))
        .join(Issue, Issue.project_id == Project.id)
        .group_by(Project.project_name)
        .order_by(func.count(Issue.id).desc())
        .limit(10)
    )).all()
    top_projects = [{"name": r[0], "count": r[1]} for r in project_rows]

    return ApiResponse(data={
        "status_distribution": status_dist,
        "priority_distribution": priority_dist,
        "daily_trend": daily_trend,
        "top_projects": top_projects,
    })
