from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──


class AgentType(str, Enum):
    claude_code = "claude_code"
    openclaw = "openclaw"
    hermes_agent = "hermes_agent"
    codex = "codex"
    windsurf = "windsurf"


class AgentCapability(str, Enum):
    remote_execution = "remote_execution"
    manual_only = "manual_only"


class MachineStatus(str, Enum):
    online = "online"
    offline = "offline"


class AgentStatus(str, Enum):
    idle = "idle"
    busy = "busy"
    offline = "offline"


class TaskStatus(str, Enum):
    pending = "pending"
    dispatched = "dispatched"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    pending_manual = "pending_manual"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


# ── Machine Schemas ──


class MachineCreate(BaseModel):
    machine_id: str = Field(..., max_length=255)
    machine_name: str = Field(..., max_length=255)
    agent_type: AgentType
    agent_capability: AgentCapability
    agent_version: str | None = None
    project_id: str | None = Field(default=None, max_length=255, description="关联的项目ID，不存在则自动创建")


class MachineResponse(BaseModel):
    id: uuid.UUID
    machine_id: str
    machine_name: str
    agent_type: AgentType
    agent_capability: AgentCapability
    agent_version: str | None
    status: MachineStatus
    is_enabled: bool = True
    agent_status: AgentStatus = AgentStatus.offline
    last_poll_at: datetime | None
    registered_at: datetime
    pending_task_count: int = 0

    model_config = {"from_attributes": True}


class MachineListResponse(BaseModel):
    id: uuid.UUID
    machine_id: str
    machine_name: str
    agent_type: AgentType
    agent_capability: AgentCapability
    status: MachineStatus
    is_enabled: bool = True
    agent_status: AgentStatus = AgentStatus.offline
    last_poll_at: datetime | None

    model_config = {"from_attributes": True}


class MachineDashboardResponse(BaseModel):
    id: uuid.UUID
    machine_id: str
    machine_name: str
    agent_type: AgentType
    agent_capability: AgentCapability
    status: MachineStatus
    is_enabled: bool = True
    agent_status: AgentStatus = AgentStatus.offline
    last_poll_at: datetime | None
    running_tasks: list["TaskListResponse"] = []
    completed_tasks_count: int = 0

    model_config = {"from_attributes": True}


class MachineUpdateStatus(BaseModel):
    is_enabled: bool | None = None
    status: MachineStatus | None = None
    agent_status: AgentStatus | None = None


# ── Task Schemas ──


class TaskCreate(BaseModel):
    instruction: str = Field(..., max_length=5000)
    project_id: uuid.UUID | None = None
    target_machine_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None


class TaskResultSubmit(BaseModel):
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    error_type: str | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    task_id: str
    instruction: str
    status: TaskStatus
    project_id: uuid.UUID | None
    target_machine_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: dict[str, Any] = {}
    error_message: str | None = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    id: uuid.UUID
    task_id: str
    instruction: str
    status: TaskStatus
    project_id: uuid.UUID | None
    target_machine_id: uuid.UUID | None
    created_at: datetime
    error_message: str | None = None

    model_config = {"from_attributes": True}


class PollTaskResponse(BaseModel):
    id: uuid.UUID
    task_id: str
    instruction: str
    status: TaskStatus
    project_id: uuid.UUID | None = None
    agent_capability: str = ""

    model_config = {"from_attributes": True}


# ── Project Schemas ──


class ProjectCreate(BaseModel):
    project_name: str = Field(..., max_length=255)
    root_path: str | None = None
    idle_threshold_hours: int = 48
    reminder_interval_hours: int = 24


class ProjectUpdate(BaseModel):
    project_name: str | None = None
    root_path: str | None = None
    idle_threshold_hours: int | None = None
    reminder_interval_hours: int | None = None
    is_archived: bool | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    project_id: str
    project_name: str
    root_path: str | None
    idle_threshold_hours: int
    reminder_interval_hours: int
    last_activity_at: datetime | None
    is_archived: bool
    created_at: datetime
    idle_hours: float | None = None

    model_config = {"from_attributes": True}


# ── Generic Response Wrapper ──


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = "ok"


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: str
    message: str


class PollResponse(BaseModel):
    machine: MachineListResponse
    tasks: list[PollTaskResponse]
