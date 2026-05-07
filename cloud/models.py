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
    status: Mapped[str] = mapped_column(String(20), default="offline")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    agent_status: Mapped[str] = mapped_column(String(20), default="offline")
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(), ForeignKey("projects.id"), nullable=True
    )
    last_poll_at: Mapped[datetime | None] = mapped_column(nullable=True)
    registered_at: Mapped[datetime] = mapped_column(default=utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="target_machine")
    project: Mapped[Project | None] = relationship()

    __table_args__ = (
        Index("idx_machines_status", "status"),
        Index("idx_machines_agent_type", "agent_type"),
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

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    target_machine: Mapped[Machine | None] = relationship(back_populates="tasks")
    project: Mapped[Project | None] = relationship(back_populates="tasks")
    template: Mapped["TaskTemplate | None"] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_target", "target_machine_id"),
        Index("idx_tasks_project", "project_id"),
        Index("idx_tasks_template", "template_id"),
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
