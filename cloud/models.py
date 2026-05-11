from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Boolean, Index, ForeignKey, JSON, TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class UUID(TypeDecorator):
    """Platform-independent UUID type. Uses PG UUID on PostgreSQL, CHAR(32) elsewhere."""
    impl = CHAR
    cache_ok = True

    def __init__(self):
        super().__init__(length=32)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, uuid.UUID):
                return value.hex
            return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


def utcnow():
    return datetime.now(timezone.utc)


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    machine_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    machine_name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_capability: Mapped[str] = mapped_column(String(20), nullable=False)
    agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    available_agents: Mapped[list[dict]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    agent_status: Mapped[str] = mapped_column(String(20), default="offline")
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("projects.id"), nullable=True
    )
    api_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(nullable=True)
    registered_at: Mapped[datetime] = mapped_column(default=utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="target_machine")
    project: Mapped["Project | None"] = relationship()
    agents: Mapped[list["Agent"]] = relationship(back_populates="machine")

    __table_args__ = (
        Index("idx_machines_status", "status"),
        Index("idx_machines_agent_type", "agent_type"),
        Index("idx_machines_api_key", "api_key"),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    root_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    idle_threshold_hours: Mapped[int] = mapped_column(Integer, default=48)
    reminder_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_activity_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
    issues: Mapped[list["Issue"]] = relationship(back_populates="project")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    assignee_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("projects.id"), nullable=True
    )
    parent_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("issues.id"), nullable=True
    )
    # Agent CLI to use for auto-dispatched task
    agent_cli_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    project: Mapped[Project | None] = relationship(back_populates="issues")
    tasks: Mapped[list["Task"]] = relationship(back_populates="issue")
    parent_issue: Mapped["Issue | None"] = relationship(
        "Issue", remote_side="Issue.id", back_populates="sub_issues"
    )
    sub_issues: Mapped[list["Issue"]] = relationship(
        "Issue", back_populates="parent_issue"
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="issue", order_by="Comment.created_at"
    )
    labels: Mapped[list["Label"]] = relationship(
        secondary="issue_labels", back_populates="issues"
    )
    outgoing_deps: Mapped[list["IssueDependency"]] = relationship(
        "IssueDependency",
        foreign_keys="IssueDependency.issue_id",
        back_populates="issue",
    )
    incoming_deps: Mapped[list["IssueDependency"]] = relationship(
        "IssueDependency",
        foreign_keys="IssueDependency.depends_on_issue_id",
        back_populates="depends_on",
    )

    __table_args__ = (
        Index("idx_issues_status", "status"),
        Index("idx_issues_project", "project_id"),
        Index("idx_issues_parent", "parent_issue_id"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending")

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("projects.id"), nullable=True
    )
    target_machine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("machines.id"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("templates.id"), nullable=True
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("issues.id"), nullable=True
    )
    # Agent CLI to use for this task (from machine's available_agents)
    agent_cli_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Session resumption fields (inspired by Multica PinTaskSession)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_dir: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Real-time progress output (streaming stdout/stderr during execution)
    progress_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retry fields
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=0)

    target_machine: Mapped[Machine | None] = relationship(back_populates="tasks")
    project: Mapped[Project | None] = relationship(back_populates="tasks")
    template: Mapped["TaskTemplate | None"] = relationship(back_populates="tasks")
    issue: Mapped["Issue | None"] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_target", "target_machine_id"),
        Index("idx_tasks_project", "project_id"),
        Index("idx_tasks_template", "template_id"),
        Index("idx_tasks_issue", "issue_id"),
    )


class TaskTemplate(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="template")

    __table_args__ = (
        Index("idx_templates_category", "category"),
    )


class Agent(Base):
    """Agent (智能体) binds to a Machine and defines HOW to execute tasks.

    Inspired by Multica's Agent model: multiple agents can share one machine
    (agent CLI), each with different instructions, model, skills, and MCP config.
    """

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("machines.id"), nullable=False
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_env: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    custom_args: Mapped[list | None] = mapped_column(JSON, nullable=True)
    mcp_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bound_cli_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bound_cli_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, default=3)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    machine: Mapped[Machine | None] = relationship()
    skills: Mapped[list["Skill"]] = relationship(
        secondary="agent_skills", back_populates="agents"
    )

    __table_args__ = (
        Index("idx_agents_machine", "machine_id"),
        Index("idx_agents_enabled", "is_enabled"),
    )


class Skill(Base):
    """Skill defines a capability that can be bound to multiple agents."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    agents: Mapped[list["Agent"]] = relationship(
        secondary="agent_skills", back_populates="skills"
    )

    __table_args__ = (
        Index("idx_skills_name", "name"),
        Index("idx_skills_category", "category"),
    )


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("agents.id"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("skills.id"), primary_key=True
    )


class IssueDependency(Base):
    __tablename__ = "issue_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("issues.id"), nullable=False
    )
    depends_on_issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("issues.id"), nullable=False
    )
    dependency_type: Mapped[str] = mapped_column(
        String(20), default="blocks"
    )  # blocks, blocked_by, related
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    issue: Mapped["Issue"] = relationship(
        "Issue",
        foreign_keys=[issue_id],
        back_populates="outgoing_deps",
    )
    depends_on: Mapped["Issue"] = relationship(
        "Issue",
        foreign_keys=[depends_on_issue_id],
        back_populates="incoming_deps",
    )

    __table_args__ = (
        Index("idx_dep_issue", "issue_id"),
        Index("idx_dep_depends_on", "depends_on_issue_id"),
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("issues.id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("comments.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    issue: Mapped["Issue"] = relationship(back_populates="comments")
    parent: Mapped["Comment | None"] = relationship(
        "Comment", remote_side="Comment.id", back_populates="replies"
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="parent"
    )

    __table_args__ = (
        Index("idx_comments_issue", "issue_id"),
        Index("idx_comments_parent", "parent_id"),
    )


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    issues: Mapped[list["Issue"]] = relationship(
        secondary="issue_labels", back_populates="labels"
    )

    __table_args__ = (Index("idx_label_name", "name"),)


class IssueLabel(Base):
    __tablename__ = "issue_labels"

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("issues.id"), primary_key=True
    )
    label_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("labels.id"), primary_key=True
    )


class TaskLog(Base):
    """Task execution event log (inspired by Multica task_logs)."""

    __tablename__ = "task_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("tasks.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # created, dispatched, running, completed, failed, retrying, progress
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    task: Mapped["Task"] = relationship()

    __table_args__ = (
        Index("idx_task_logs_task", "task_id"),
        Index("idx_task_logs_event", "event_type"),
    )


class InboxItem(Base):
    """Inbox: notifications and messages for users."""

    __tablename__ = "inbox_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(
        String(50), default="notification"
    )  # notification, alert, info
    source_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # task, issue, autopilot, system
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("idx_inbox_read", "is_read"),
        Index("idx_inbox_type", "item_type"),
        Index("idx_inbox_created", "created_at"),
    )


class Autopilot(Base):
    """Autopilot: scheduled/recurring task creation (inspired by Multica autopilots)."""

    __tablename__ = "autopilots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("projects.id"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("templates.id"), nullable=True
    )
    target_machine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("machines.id"), nullable=True
    )
    # Trigger config
    trigger_type: Mapped[str] = mapped_column(
        String(20), default="cron"
    )  # cron, interval, webhook, manual
    cron_expr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Runtime
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    project: Mapped["Project | None"] = relationship()
    template: Mapped["TaskTemplate | None"] = relationship()
    target_machine: Mapped["Machine | None"] = relationship()

    __table_args__ = (
        Index("idx_autopilots_project", "project_id"),
        Index("idx_autopilots_enabled", "is_enabled"),
        Index("idx_autopilots_next_run", "next_run_at"),
    )


class ApiBan(Base):
    """Ban an IP address or API key from accessing the system."""

    __tablename__ = "api_bans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "ip" or "key"
    target_value: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("idx_api_bans_type_value", "target_type", "target_value"),
        Index("idx_api_bans_active", "is_active"),
    )
