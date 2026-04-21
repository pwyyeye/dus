"""APScheduler-based reminder scheduler for stalled projects and timed-out tasks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import async_session
from models import Project, Task
from notifier import send_wechat_markdown

logger = logging.getLogger(__name__)

# Module-level scheduler instance
_scheduler: AsyncIOScheduler | None = None


async def _check_stalled_projects() -> None:
    """Check for stalled projects and send reminders.

    Runs every hour. Finds unarchived projects where:
    - last_activity_at < NOW() - idle_threshold_hours
    Sends WeChat reminder for each stalled project.
    """
    logger.info("Running stalled projects check...")

    async with async_session() as db:
        now = datetime.now(timezone.utc)

        # Query unarchived projects
        stmt = select(Project).where(Project.is_archived == False)
        result = await db.execute(stmt)
        projects = result.scalars().all()

        for project in projects:
            if project.last_activity_at is None:
                continue

            # Calculate idle time
            last_activity = project.last_activity_at
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)

            idle_delta = now - last_activity
            idle_hours = idle_delta.total_seconds() / 3600

            if idle_hours > project.idle_threshold_hours:
                # Project is stalled - send reminder
                threshold_hours = project.idle_threshold_hours
                reminder_interval = project.reminder_interval_hours

                # Check deduplication - use result dict for last_reminder_at
                last_reminder = project.result.get("last_reminder_at") if project.result else None
                if last_reminder and reminder_interval > 0:
                    last_reminder_time = datetime.fromisoformat(last_reminder)
                    hours_since_reminder = (now - last_reminder_time).total_seconds() / 3600
                    if hours_since_reminder < reminder_interval:
                        logger.debug(
                            f"Skipping reminder for project {project.project_id} "
                            f"(last reminder {hours_since_reminder:.1f}h ago, "
                            f"interval={reminder_interval}h)"
                        )
                        continue

                # Build reminder message
                idle_str = f"{idle_hours:.1f}"
                threshold_str = f"{threshold_hours}"
                content = (
                    f"**项目名称**: {project.project_name}\n\n"
                    f"**项目路径**: {project.root_path or 'N/A'}\n\n"
                    f"**闲置时间**: {idle_str} 小时\n"
                    f"**阈值**: {threshold_str} 小时\n\n"
                    f"⚠️ 项目已超过闲置阈值，请检查。"
                )

                title = f"⚠️ 项目闲置提醒: {project.project_name}"
                success = await send_wechat_markdown(title, content)

                # Update last_reminder_at in result
                if project.result is None:
                    project.result = {}
                project.result["last_reminder_at"] = now.isoformat()
                if success:
                    logger.info(f"Sent stalled project reminder: {project.project_id}")


async def _check_timed_out_tasks() -> None:
    """Check for timed-out tasks and send reminders.

    Runs every 5 minutes. Finds tasks where:
    - status = 'running'
    - started_at + timeout_seconds < NOW()
    Sends timeout reminder and marks task as failed.
    """
    logger.info("Running timed-out tasks check...")

    async with async_session() as db:
        now = datetime.now(timezone.utc)

        # Query running tasks with started_at set
        stmt = select(Task).where(
            and_(
                Task.status == "running",
                Task.started_at.isnot(None),
            )
        )
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        for task in tasks:
            if task.started_at is None:
                continue

            # Calculate timeout
            started = task.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)

            # Get timeout_seconds from task result or default to 3600
            timeout_seconds = 3600
            if task.result and "timeout_seconds" in task.result:
                timeout_seconds = task.result.get("timeout_seconds", 3600)

            elapsed = (now - started).total_seconds()
            if elapsed > timeout_seconds:
                # Task has timed out

                # Check deduplication - don't repeat if within reminder_interval_hours
                # Use reminder_interval_hours from the associated project, default 24h
                reminder_interval_hours = 24
                project = task.project
                if project:
                    reminder_interval_hours = project.reminder_interval_hours

                last_reminder = None
                if task.result:
                    last_reminder = task.result.get("last_reminder_at")

                if last_reminder and reminder_interval_hours > 0:
                    last_reminder_time = datetime.fromisoformat(last_reminder)
                    hours_since_reminder = (now - last_reminder_time).total_seconds() / 3600
                    if hours_since_reminder < reminder_interval_hours:
                        logger.debug(
                            f"Skipping timeout reminder for task {task.task_id} "
                            f"(last reminder {hours_since_reminder:.1f}h ago, "
                            f"interval={reminder_interval_hours}h)"
                        )
                        continue

                # Build timeout message
                machine_name = task.target_machine.machine_name if task.target_machine else "Unknown"
                project_name = task.project.project_name if task.project else "Unknown"
                project_root = task.project.root_path if task.project else "Unknown"
                elapsed_str = f"{elapsed:.0f}"
                timeout_str = f"{timeout_seconds}"

                content = (
                    f"**任务指令**: {task.instruction}\n\n"
                    f"**所属机器**: {machine_name}\n"
                    f"**项目名称**: {project_name}\n"
                    f"**项目路径**: {project_root}\n\n"
                    f"⏱️ 任务执行超时\n"
                    f"**已运行**: {elapsed_str} 秒\n"
                    f"**超时设置**: {timeout_str} 秒\n\n"
                    f"请手动处理。"
                )

                title = f"⏱️ 任务执行超时: {task.task_id}"
                await send_wechat_markdown(title, content)

                # Mark task as failed
                task.status = "failed"
                task.completed_at = now
                if task.result is None:
                    task.result = {}
                task.result["last_reminder_at"] = now.isoformat()
                task.result["error_type"] = "timeout"
                task.result["exit_code"] = -1

                logger.info(f"Marked task as failed due to timeout: {task.task_id}")


def start_scheduler() -> AsyncIOScheduler:
    """Create and start the APScheduler instance."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler()

    # Project stall check: every 1 hour
    _scheduler.add_job(
        _check_stalled_projects,
        trigger=IntervalTrigger(hours=1),
        id="check_stalled_projects",
        name="Check stalled projects",
        replace_existing=True,
    )

    # Task timeout check: every 5 minutes
    _scheduler.add_job(
        _check_timed_out_tasks,
        trigger=IntervalTrigger(minutes=5),
        id="check_timed_out_tasks",
        name="Check timed-out tasks",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("APScheduler started")
    return _scheduler


def stop_scheduler() -> None:
    """Stop the APScheduler instance."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler stopped")
