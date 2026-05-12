from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ──


class AgentType(str, Enum):
    claude_code = "claude_code"
    openclaw = "openclaw"
    hermes_agent = "hermes_agent"
    codex = "codex"
    kimi = "kimi"


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


class IssueStatus(str, Enum):
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    blocked = "blocked"
    cancelled = "cancelled"


class IssuePriority(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class DependencyType(str, Enum):
    blocks = "blocks"
    blocked_by = "blocked_by"
    related = "related"


# ── Machine Schemas ──


class MachineCreate(BaseModel):
    machine_id: str = Field(..., max_length=255)
    machine_name: str = Field(..., max_length=255)
    agent_type: AgentType
    agent_capability: AgentCapability
    agent_version: str | None = None
    project_id: str | None = Field(default=None, max_length=255, description="关联的项目ID，不存在则自动创建")
    project_root: str | None = Field(default=None, max_length=1024, description="项目根目录路径")
    available_agents: list[dict] | None = Field(default=None, description="设备上可用的agent CLI列表")

    @field_validator("machine_id")
    @classmethod
    def validate_machine_id(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("machine_id 只能包含字母、数字、下划线和连字符")
        return v


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
    project_id: uuid.UUID | None = None
    last_poll_at: datetime | None
    registered_at: datetime
    pending_task_count: int = 0
    available_agents: Any | None = None

    model_config = {"from_attributes": True}


class MachineListResponse(BaseModel):
    id: uuid.UUID
    machine_id: str
    machine_name: str
    agent_type: AgentType
    agent_capability: AgentCapability
    agent_version: str | None = None
    status: MachineStatus
    is_enabled: bool = True
    agent_status: AgentStatus = AgentStatus.offline
    project_id: uuid.UUID | None = None
    last_poll_at: datetime | None
    available_agents: Any | None = None

    model_config = {"from_attributes": True}


class MachineDashboardResponse(BaseModel):
    id: uuid.UUID
    machine_id: str
    machine_name: str
    agent_type: AgentType
    agent_capability: AgentCapability
    agent_version: str | None = None
    status: MachineStatus
    is_enabled: bool = True
    agent_status: AgentStatus = AgentStatus.offline
    project_id: uuid.UUID | None = None
    last_poll_at: datetime | None
    running_tasks: list["TaskListResponse"] = []
    completed_tasks_count: int = 0

    model_config = {"from_attributes": True}


class MachineUpdateStatus(BaseModel):
    is_enabled: bool | None = None
    status: MachineStatus | None = None
    agent_status: AgentStatus | None = None
    agent_version: str | None = None


class MachineRegisterResponse(BaseModel):
    id: uuid.UUID
    machine_id: str
    machine_name: str
    agent_type: AgentType
    agent_capability: AgentCapability
    agent_version: str | None = None
    api_key: str
    status: MachineStatus
    project_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


# ── Task Schemas ──


class TaskCreate(BaseModel):
    instruction: str = Field(..., max_length=5000)
    project_id: uuid.UUID | None = None
    target_machine_id: uuid.UUID | None = None
    issue_id: uuid.UUID | None = None
    agent_cli_id: str | None = Field(default=None, description="Agent CLI类型，如 claude_code, codex, openclaw, kimi")
    max_retries: int = Field(default=0, ge=0, le=10)


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None


class TaskResultSubmit(BaseModel):
    exit_code: int = 0
    stdout: str = Field(default="", max_length=50000)
    stderr: str = Field(default="", max_length=50000)
    error_type: str | None = None
    session_id: str | None = None
    work_dir: str | None = None


class TaskProgressSubmit(BaseModel):
    stdout_delta: str = Field(default="", max_length=10000)
    stderr_delta: str = Field(default="", max_length=10000)
    progress_pct: int | None = Field(default=None, ge=0, le=100)


class TaskResponse(BaseModel):
    id: uuid.UUID
    task_id: str
    instruction: str
    status: TaskStatus
    project_id: uuid.UUID | None
    target_machine_id: uuid.UUID | None
    issue_id: uuid.UUID | None
    agent_cli_id: str | None = None
    template_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: dict[str, Any] = {}
    error_message: str | None = None
    session_id: str | None = None
    work_dir: str | None = None
    progress_output: str | None = None
    retry_count: int = 0
    max_retries: int = 0

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    id: uuid.UUID
    task_id: str
    instruction: str
    status: TaskStatus
    project_id: uuid.UUID | None
    target_machine_id: uuid.UUID | None
    issue_id: uuid.UUID | None
    agent_cli_id: str | None = None
    created_at: datetime
    error_message: str | None = None
    retry_count: int = 0
    max_retries: int = 0

    model_config = {"from_attributes": True}


class AgentConfig(BaseModel):
    """Agent configuration passed to the bridge during task dispatch."""
    agent_id: str
    agent_type: str | None = None
    name: str
    instructions: str | None = None
    model: str | None = None
    custom_env: dict | None = None
    custom_args: list | None = None
    mcp_config: dict | None = None


class PollTaskResponse(BaseModel):
    id: uuid.UUID
    task_id: str
    instruction: str
    status: TaskStatus
    project_id: uuid.UUID | None = None
    agent_capability: str = ""
    agent_cli_id: str | None = None
    issue_id: uuid.UUID | None = None
    prior_session_id: str | None = None
    prior_work_dir: str | None = None
    agent_config: AgentConfig | None = None

    model_config = {"from_attributes": True}


# ── Issue Schemas ──


class IssueCreate(BaseModel):
    title: str = Field(..., max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    status: IssueStatus = IssueStatus.todo
    priority: IssuePriority = IssuePriority.medium
    assignee_type: str | None = Field(default=None, max_length=20, description="'machine' 或 'agent'")
    assignee_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    parent_issue_id: uuid.UUID | None = None
    label_ids: list[uuid.UUID] = Field(default_factory=list)
    agent_cli_id: str | None = Field(default=None, description="Agent CLI类型，如 claude_code, codex, openclaw, kimi")


class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    status: IssueStatus | None = None
    priority: IssuePriority | None = None
    assignee_type: str | None = Field(default=None, max_length=20, description="'machine' 或 'agent'")
    assignee_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    parent_issue_id: uuid.UUID | None = None
    label_ids: list[uuid.UUID] | None = None
    agent_cli_id: str | None = Field(default=None, description="Agent CLI类型")


class IssueResponse(BaseModel):
    id: uuid.UUID
    issue_id: str
    title: str
    description: str | None
    status: IssueStatus
    priority: IssuePriority
    assignee_type: str | None
    assignee_id: uuid.UUID | None
    project_id: uuid.UUID | None
    parent_issue_id: uuid.UUID | None
    agent_cli_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IssueListResponse(BaseModel):
    id: uuid.UUID
    issue_id: str
    title: str
    status: IssueStatus
    priority: IssuePriority
    assignee_type: str | None
    assignee_id: uuid.UUID | None
    project_id: uuid.UUID | None
    parent_issue_id: uuid.UUID | None
    agent_cli_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IssueDetailResponse(IssueResponse):
    tasks: list["TaskListResponse"] = []
    sub_issues: list["IssueListResponse"] = []
    labels: list["LabelResponse"] = []
    dependencies: list["IssueDependencyResponse"] = []
    comments: list["CommentResponse"] = []


class IssueDependencyCreate(BaseModel):
    depends_on_issue_id: uuid.UUID
    dependency_type: DependencyType = DependencyType.blocks


class IssueDependencyResponse(BaseModel):
    id: uuid.UUID
    issue_id: uuid.UUID
    depends_on_issue_id: uuid.UUID
    dependency_type: DependencyType
    created_at: datetime
    depends_on: "IssueListResponse | None" = None

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    issue_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    content: str = Field(..., max_length=10000)
    author_name: str | None = Field(default=None, max_length=100)


class CommentUpdate(BaseModel):
    content: str | None = Field(default=None, max_length=10000)


class CommentResponse(BaseModel):
    id: uuid.UUID
    issue_id: uuid.UUID
    parent_id: uuid.UUID | None
    content: str
    author_name: str | None
    created_at: datetime
    replies: list["CommentResponse"] = []

    model_config = {"from_attributes": True}


class LabelCreate(BaseModel):
    name: str = Field(..., max_length=100)
    color: str | None = Field(default=None, max_length=7)


class LabelResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Project Schemas ──


class ProjectCreate(BaseModel):
    project_name: str = Field(..., max_length=255)
    root_path: str | None = None
    idle_threshold_hours: int = 48
    reminder_interval_hours: int = 24

    @field_validator("root_path")
    @classmethod
    def validate_root_path(cls, v: str | None) -> str | None:
        if v and ".." in v:
            raise ValueError("root_path 不允许包含 '..' 路径穿越")
        return v


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
    is_exceeding_threshold: bool | None = None

    model_config = {"from_attributes": True}


# ── Generic Response Wrapper ──


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = "ok"
    meta: dict | None = None


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: str
    message: str


class PollResponse(BaseModel):
    machine: MachineListResponse
    tasks: list[PollTaskResponse]


# ── TaskLog Schemas ──


class TaskLogCreate(BaseModel):
    task_id: uuid.UUID
    event_type: str = Field(..., max_length=50)
    message: str | None = None
    metadata_json: dict | None = None


class TaskLogResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    event_type: str
    message: str | None
    metadata_json: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Autopilot Schemas ──


class AutopilotCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    project_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    target_machine_id: uuid.UUID | None = None
    trigger_type: str = Field(default="cron", max_length=20)
    cron_expr: str | None = Field(default=None, max_length=100)
    interval_minutes: int | None = Field(default=None, ge=1)
    webhook_secret: str | None = Field(default=None, max_length=255)


class AutopilotUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    target_machine_id: uuid.UUID | None = None
    trigger_type: str | None = None
    cron_expr: str | None = None
    interval_minutes: int | None = None
    is_enabled: bool | None = None


class AutopilotResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    project_id: uuid.UUID | None
    template_id: uuid.UUID | None
    target_machine_id: uuid.UUID | None
    trigger_type: str
    cron_expr: str | None
    interval_minutes: int | None
    is_enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    run_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Inbox Schemas ──


class InboxItemCreate(BaseModel):
    title: str = Field(..., max_length=500)
    message: str | None = None
    item_type: str = Field(default="notification", max_length=50)
    source_type: str | None = Field(default=None, max_length=50)
    source_id: str | None = None


class InboxItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    message: str | None
    item_type: str
    source_type: str | None
    source_id: str | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Skill Schemas ──


class SkillCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = None
    category: str | None = Field(default=None, max_length=50)
    config: dict | None = None


class SkillResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    config: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Template Schemas ──


class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    instruction: str = Field(..., max_length=5000)
    category: str | None = Field(default=None, max_length=50)


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    instruction: str | None = None
    category: str | None = None
    is_enabled: bool | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    instruction: str
    category: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Agent Schemas ──


class AgentCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    machine_id: uuid.UUID
    instructions: str | None = Field(default=None, max_length=10000)
    model: str | None = Field(default=None, max_length=100)
    custom_env: dict | None = None
    custom_args: list[str] | None = None
    mcp_config: dict | None = None
    bound_cli_id: str | None = None
    max_concurrent_tasks: int = Field(default=3, ge=1, le=20)
    skill_ids: list[uuid.UUID] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    machine_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=10000)
    model: str | None = Field(default=None, max_length=100)
    custom_env: dict | None = None
    custom_args: list[str] | None = None
    mcp_config: dict | None = None
    bound_cli_id: str | None = None
    max_concurrent_tasks: int | None = Field(default=None, ge=1, le=20)
    is_enabled: bool | None = None
    skill_ids: list[uuid.UUID] | None = None


class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    machine_id: uuid.UUID
    instructions: str | None
    model: str | None
    custom_env: dict | None
    custom_args: list[str] | None
    mcp_config: dict | None
    bound_cli_id: str | None
    bound_cli_type: str | None
    max_concurrent_tasks: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    machine: MachineListResponse | None = None
    skills: list["SkillResponse"] = []

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    machine_id: uuid.UUID
    model: str | None
    bound_cli_id: str | None
    bound_cli_type: str | None
    max_concurrent_tasks: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    machine: MachineListResponse | None = None
    skills: list["SkillResponse"] = []

    model_config = {"from_attributes": True}


# ── ApiBan Schemas ──


class ApiBanCreate(BaseModel):
    target_type: str = Field(..., pattern="^(ip|key)$")
    target_value: str = Field(..., max_length=255)
    reason: str | None = Field(default=None, max_length=1000)


class ApiBanResponse(BaseModel):
    id: uuid.UUID
    target_type: str
    target_value: str
    reason: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
