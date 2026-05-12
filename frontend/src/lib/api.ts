const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "change-me-to-a-strong-random-string-at-least-32-chars";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API Error: ${res.status}`);
  }

  return res.json();
}

// ── Types ──

export interface Machine {
  id: string;
  machine_id: string;
  machine_name: string;
  agent_type: string;
  agent_capability: string;
  agent_version?: string | null;
  agent_status: "idle" | "busy" | "offline";
  status: "online" | "offline";
  is_enabled: boolean;
  last_poll_at: string | null;
  registered_at: string;
  pending_task_count?: number;
  available_agents?: Array<{ cli_id: string; agent_type: string; path: string; version: string }>;
}

export interface MachineDashboard {
  id: string;
  machine_id: string;
  machine_name: string;
  agent_type: string;
  agent_capability: string;
  agent_version?: string | null;
  agent_status: "idle" | "busy" | "offline";
  status: "online" | "offline";
  is_enabled: boolean;
  last_poll_at: string | null;
  running_tasks: Task[];
  completed_tasks_count: number;
}

export interface Task {
  id: string;
  task_id: string;
  instruction: string;
  status: "pending" | "dispatched" | "running" | "completed" | "failed" | "cancelled" | "pending_manual";
  project_id: string | null;
  target_machine_id: string | null;
  issue_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: Record<string, unknown>;
  error_message: string | null;
  progress_output: string | null;
  retry_count: number;
  max_retries: number;
}

export interface TaskLog {
  id: string;
  task_id: string;
  event_type: string;
  message: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface Autopilot {
  id: string;
  name: string;
  description: string | null;
  project_id: string | null;
  template_id: string | null;
  target_machine_id: string | null;
  trigger_type: string;
  cron_expr: string | null;
  interval_minutes: number | null;
  is_enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  created_at: string;
  updated_at: string;
}

export interface Label {
  id: string;
  name: string;
  color: string | null;
  created_at: string;
}

export interface IssueDependency {
  id: string;
  issue_id: string;
  depends_on_issue_id: string;
  dependency_type: "blocks" | "blocked_by" | "related";
  created_at: string;
  depends_on?: Issue | null;
}

export interface Comment {
  id: string;
  issue_id: string;
  parent_id: string | null;
  content: string;
  author_name: string | null;
  created_at: string;
  replies: Comment[];
}

export interface ChatMessage {
  id: string;
  chat_session_id: string;
  role: "user" | "assistant";
  content: string;
  task_id: string | null;
  created_at: string;
}

export interface Issue {
  id: string;
  issue_id: string;
  title: string;
  description: string | null;
  status: "todo" | "in_progress" | "done" | "cancelled";
  priority: "low" | "medium" | "high" | "urgent";
  assignee_type: string | null;
  assignee_id: string | null;
  project_id: string | null;
  parent_issue_id: string | null;
  agent_cli_id?: string | null;
  created_at: string;
  updated_at: string;
  tasks?: Task[];
  sub_issues?: Issue[];
  labels?: Label[];
  dependencies?: IssueDependency[];
  comments?: Comment[];
}

export interface Project {
  id: string;
  project_id: string;
  project_name: string;
  root_path: string | null;
  idle_threshold_hours: number;
  reminder_interval_hours: number;
  last_activity_at: string | null;
  is_archived: boolean;
  created_at: string;
  idle_hours: number | null;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string;
  meta?: Record<string, unknown>;
}

// ── Machine API ──

export async function fetchMachines(): Promise<Machine[]> {
  const res = await request<ApiResponse<Machine[]>>("/machines");
  return res.data;
}

export async function fetchMachine(id: string): Promise<Machine> {
  const res = await request<ApiResponse<Machine>>(`/machines/${id}`);
  return res.data;
}

export async function registerMachine(data: {
  machine_id: string;
  machine_name: string;
  agent_type: string;
  agent_capability: string;
}): Promise<Machine> {
  const res = await request<ApiResponse<Machine>>("/machines", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function fetchMachinesDashboard(): Promise<MachineDashboard[]> {
  const res = await request<ApiResponse<MachineDashboard[]>>("/machines/dashboard");
  return res.data;
}

export async function updateMachine(id: string, data: {
  is_enabled?: boolean;
  status?: string;
}): Promise<Machine> {
  const res = await request<ApiResponse<Machine>>(`/machines/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return res.data;
}

// ── Task API ──

export async function fetchTasks(params?: {
  status?: string;
  project_id?: string;
  target_machine_id?: string;
}): Promise<Task[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.target_machine_id) query.set("target_machine_id", params.target_machine_id);
  const qs = query.toString();
  const res = await request<ApiResponse<Task[]>>(`/tasks${qs ? `?${qs}` : ""}`);
  return res.data;
}

export async function fetchTask(id: string): Promise<Task> {
  const res = await request<ApiResponse<Task>>(`/tasks/${id}`);
  return res.data;
}

export async function createTask(data: {
  instruction: string;
  project_id?: string;
  target_machine_id?: string;
  agent_cli_id?: string;
  max_retries?: number;
}): Promise<Task> {
  const res = await request<ApiResponse<Task>>("/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function fetchTaskLogs(taskId: string): Promise<TaskLog[]> {
  const res = await request<ApiResponse<TaskLog[]>>(`/tasks/${taskId}/logs`);
  return res.data;
}

export async function updateTask(id: string, data: {
  status?: string;
}): Promise<Task> {
  const res = await request<ApiResponse<Task>>(`/tasks/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function cancelTask(id: string): Promise<Task> {
  return updateTask(id, { status: "cancelled" });
}

export async function fetchUnassignedTasks(params?: { limit?: number; offset?: number }): Promise<Task[]> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  const res = await request<ApiResponse<Task[]>>(`/tasks/pool${qs ? `?${qs}` : ""}`);
  return res.data;
}

export async function claimTask(taskId: string, machineId: string): Promise<Task> {
  const res = await request<ApiResponse<Task>>(`/tasks/${taskId}/claim?machine_uuid=${machineId}`, {
    method: "POST",
  });
  return res.data;
}

// ── Project API ──

export async function fetchProjects(): Promise<Project[]> {
  const res = await request<ApiResponse<Project[]>>("/projects");
  return res.data;
}

export async function fetchProject(id: string): Promise<Project> {
  const res = await request<ApiResponse<Project>>(`/projects/${id}`);
  return res.data;
}

export async function createProject(data: {
  project_name: string;
  root_path?: string;
}): Promise<Project> {
  const res = await request<ApiResponse<Project>>("/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateProject(id: string, data: {
  project_name?: string;
  root_path?: string;
  idle_threshold_hours?: number;
  reminder_interval_hours?: number;
  is_archived?: boolean;
}): Promise<Project> {
  const res = await request<ApiResponse<Project>>(`/projects/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

// ── Issue API ──

export async function fetchIssues(params?: {
  status?: string;
  project_id?: string;
  assignee_id?: string;
  label_id?: string;
  limit?: number;
  offset?: number;
}): Promise<{ issues: Issue[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.assignee_id) query.set("assignee_id", params.assignee_id);
  if (params?.label_id) query.set("label_id", params.label_id);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  const res = await request<ApiResponse<Issue[]>>(`/issues${qs ? `?${qs}` : ""}`);
  const total = typeof res.meta?.total === "number" ? res.meta.total : res.data.length;
  return { issues: res.data, total };
}

export async function fetchIssue(id: string): Promise<Issue> {
  const res = await request<ApiResponse<Issue>>(`/issues/${id}`);
  return res.data;
}

export async function createIssue(data: {
  title: string;
  description?: string;
  status?: string;
  priority?: string;
  assignee_type?: string;
  assignee_id?: string;
  project_id?: string;
  parent_issue_id?: string;
  label_ids?: string[];
  agent_cli_id?: string;
}): Promise<Issue> {
  const res = await request<ApiResponse<Issue>>("/issues", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateIssue(id: string, data: {
  title?: string;
  description?: string;
  status?: string;
  priority?: string;
  assignee_type?: string;
  assignee_id?: string;
  project_id?: string;
  parent_issue_id?: string | null;
  label_ids?: string[];
  agent_cli_id?: string;
}): Promise<Issue> {
  const res = await request<ApiResponse<Issue>>(`/issues/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteIssue(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/issues/${id}`, { method: "DELETE" });
}

export async function fetchIssueTasks(id: string): Promise<Task[]> {
  const res = await request<ApiResponse<Task[]>>(`/issues/${id}/tasks`);
  return res.data;
}

export async function addIssueDependency(issueId: string, data: {
  depends_on_issue_id: string;
  dependency_type: string;
}): Promise<IssueDependency> {
  const res = await request<ApiResponse<IssueDependency>>(`/issues/${issueId}/dependencies`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function removeIssueDependency(issueId: string, depId: string): Promise<void> {
  await request<ApiResponse<void>>(`/issues/${issueId}/dependencies/${depId}`, { method: "DELETE" });
}

// ── Comment API ──

export async function fetchIssueComments(issueId: string): Promise<Comment[]> {
  const res = await request<ApiResponse<Comment[]>>(`/comments/issue/${issueId}`);
  return res.data;
}

export async function createComment(data: {
  issue_id: string;
  content: string;
  parent_id?: string;
  author_name?: string;
}): Promise<Comment> {
  const res = await request<ApiResponse<Comment>>("/comments", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateComment(id: string, data: { content: string }): Promise<Comment> {
  const res = await request<ApiResponse<Comment>>(`/comments/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteComment(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/comments/${id}`, { method: "DELETE" });
}

// ── ChatMessage API ──

export async function fetchIssueMessages(issueId: string): Promise<ChatMessage[]> {
  const res = await request<ApiResponse<ChatMessage[]>>(`/issues/${issueId}/messages`);
  return res.data;
}

export async function appendChatMessage(taskId: string, data: {
  role: "user" | "assistant";
  content: string;
}): Promise<ChatMessage> {
  const res = await request<ApiResponse<ChatMessage>>(`/tasks/${taskId}/messages`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

// ── Label API ──

export async function fetchLabels(): Promise<Label[]> {
  const res = await request<ApiResponse<Label[]>>("/labels");
  return res.data;
}

export async function createLabel(data: { name: string; color?: string }): Promise<Label> {
  const res = await request<ApiResponse<Label>>("/labels", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateLabel(id: string, data: { name?: string; color?: string }): Promise<Label> {
  const res = await request<ApiResponse<Label>>(`/labels/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteLabel(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/labels/${id}`, { method: "DELETE" });
}

export async function addLabelToIssue(issueId: string, labelId: string): Promise<void> {
  await request<ApiResponse<void>>(`/labels/issues/${issueId}/labels/${labelId}`, { method: "POST" });
}

export async function removeLabelFromIssue(issueId: string, labelId: string): Promise<void> {
  await request<ApiResponse<void>>(`/labels/issues/${issueId}/labels/${labelId}`, { method: "DELETE" });
}

// ── Template API ──

export interface Template {
  id: string;
  name: string;
  description: string | null;
  instruction: string;
  category: string | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export async function fetchTemplates(): Promise<Template[]> {
  const res = await request<ApiResponse<Template[]>>("/templates");
  return res.data;
}

export async function createTemplate(data: {
  name: string;
  description?: string;
  instruction: string;
  category?: string;
}): Promise<Template> {
  const res = await request<ApiResponse<Template>>("/templates", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

// ── Skill Types ──

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  config: Record<string, unknown> | null;
  created_at: string;
}

export interface ActivityDay {
  date: string;
  count: number;
}

// ── Agent API ──

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  machine_id: string;
  instructions: string | null;
  model: string | null;
  custom_env: Record<string, string> | null;
  custom_args: string[] | null;
  mcp_config: Record<string, unknown> | null;
  bound_cli_id: string | null;
  bound_cli_type: string | null;
  max_concurrent_tasks: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
  machine?: Machine | null;
  skills: Skill[];
}

export async function fetchAgents(params?: {
  machine_id?: string;
  is_enabled?: boolean;
}): Promise<Agent[]> {
  const query = new URLSearchParams();
  if (params?.machine_id) query.set("machine_id", params.machine_id);
  if (params?.is_enabled !== undefined) query.set("is_enabled", String(params.is_enabled));
  const qs = query.toString();
  const res = await request<ApiResponse<Agent[]>>(`/agents${qs ? `?${qs}` : ""}`);
  return res.data;
}

export async function fetchAgent(id: string): Promise<Agent> {
  const res = await request<ApiResponse<Agent>>(`/agents/${id}`);
  return res.data;
}

export async function createAgent(data: {
  name: string;
  description?: string;
  machine_id: string;
  instructions?: string;
  model?: string;
  custom_env?: Record<string, string>;
  custom_args?: string[];
  mcp_config?: Record<string, unknown>;
  bound_cli_id?: string;
  max_concurrent_tasks?: number;
  skill_ids?: string[];
}): Promise<Agent> {
  const res = await request<ApiResponse<Agent>>("/agents", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateAgent(id: string, data: {
  name?: string;
  description?: string;
  machine_id?: string;
  instructions?: string;
  model?: string;
  custom_env?: Record<string, string>;
  custom_args?: string[];
  mcp_config?: Record<string, unknown>;
  bound_cli_id?: string;
  max_concurrent_tasks?: number;
  is_enabled?: boolean;
  skill_ids?: string[];
}): Promise<Agent> {
  const res = await request<ApiResponse<Agent>>(`/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteAgent(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/agents/${id}`, { method: "DELETE" });
}

export async function fetchAgentActivity(id: string, days: number = 30): Promise<ActivityDay[]> {
  const res = await request<ApiResponse<ActivityDay[]>>(`/agents/${id}/activity?days=${days}`);
  return res.data;
}

// ── Skill API ──

export async function fetchSkills(params?: { category?: string }): Promise<Skill[]> {
  const query = new URLSearchParams();
  if (params?.category) query.set("category", params.category);
  const qs = query.toString();
  const res = await request<ApiResponse<Skill[]>>(`/skills${qs ? `?${qs}` : ""}`);
  return res.data;
}

export async function fetchSkill(id: string): Promise<Skill> {
  const res = await request<ApiResponse<Skill>>(`/skills/${id}`);
  return res.data;
}

export async function createSkill(data: {
  name: string;
  description?: string;
  category?: string;
  config?: Record<string, unknown>;
}): Promise<Skill> {
  const res = await request<ApiResponse<Skill>>("/skills", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateSkill(id: string, data: {
  name?: string;
  description?: string;
  category?: string;
  config?: Record<string, unknown>;
}): Promise<Skill> {
  const res = await request<ApiResponse<Skill>>(`/skills/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteSkill(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/skills/${id}`, { method: "DELETE" });
}

// ── Autopilot API ──

export async function fetchAutopilots(params?: {
  project_id?: string;
  is_enabled?: boolean;
}): Promise<Autopilot[]> {
  const query = new URLSearchParams();
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.is_enabled !== undefined) query.set("is_enabled", String(params.is_enabled));
  const qs = query.toString();
  const res = await request<ApiResponse<Autopilot[]>>(`/autopilots${qs ? `?${qs}` : ""}`);
  return res.data;
}

export async function fetchAutopilot(id: string): Promise<Autopilot> {
  const res = await request<ApiResponse<Autopilot>>(`/autopilots/${id}`);
  return res.data;
}

export async function createAutopilot(data: {
  name: string;
  description?: string;
  project_id?: string;
  template_id?: string;
  target_machine_id?: string;
  trigger_type?: string;
  cron_expr?: string;
  interval_minutes?: number;
  webhook_secret?: string;
}): Promise<Autopilot> {
  const res = await request<ApiResponse<Autopilot>>("/autopilots", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateAutopilot(id: string, data: {
  name?: string;
  description?: string;
  project_id?: string;
  template_id?: string;
  target_machine_id?: string;
  trigger_type?: string;
  cron_expr?: string;
  interval_minutes?: number;
  is_enabled?: boolean;
}): Promise<Autopilot> {
  const res = await request<ApiResponse<Autopilot>>(`/autopilots/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteAutopilot(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/autopilots/${id}`, { method: "DELETE" });
}

export async function triggerAutopilot(id: string): Promise<Autopilot> {
  const res = await request<ApiResponse<Autopilot>>(`/autopilots/${id}/run`, {
    method: "POST",
  });
  return res.data;
}

// ── Inbox API ──

export interface InboxItem {
  id: string;
  title: string;
  message: string | null;
  item_type: string;
  source_type: string | null;
  source_id: string | null;
  is_read: boolean;
  created_at: string;
}

export async function fetchInboxItems(params?: {
  is_read?: boolean;
  item_type?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: InboxItem[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.is_read !== undefined) query.set("is_read", String(params.is_read));
  if (params?.item_type) query.set("item_type", params.item_type);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  const res = await request<ApiResponse<InboxItem[]>>(`/inbox${qs ? `?${qs}` : ""}`);
  const total = typeof res.meta?.total === "number" ? res.meta.total : res.data.length;
  return { items: res.data, total };
}

export async function fetchUnreadCount(): Promise<number> {
  const res = await request<ApiResponse<{ count: number }>>("/inbox/unread-count");
  return res.data.count;
}

export async function markInboxRead(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/inbox/${id}/read`, { method: "PUT" });
}

export async function markAllInboxRead(): Promise<void> {
  await request<ApiResponse<void>>("/inbox/read-all", { method: "POST" });
}

export async function deleteInboxItem(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/inbox/${id}`, { method: "DELETE" });
}

// ── Analytics API ──

export interface AnalyticsOverview {
  counts: {
    tasks: number;
    issues: number;
    machines: number;
    agents: number;
    projects: number;
  };
  recent: {
    tasks_7d: number;
    issues_7d: number;
  };
  task_success_rate: number;
  online_machines: number;
}

export interface TaskStats {
  status_distribution: Record<string, number>;
  daily_trend: { date: string; count: number }[];
  top_machines: { name: string; count: number }[];
}

export interface IssueStats {
  status_distribution: Record<string, number>;
  priority_distribution: Record<string, number>;
  daily_trend: { date: string; count: number }[];
  top_projects: { name: string; count: number }[];
}

export async function fetchAnalyticsOverview(): Promise<AnalyticsOverview> {
  const res = await request<ApiResponse<AnalyticsOverview>>("/analytics/overview");
  return res.data;
}

export async function fetchTaskStats(): Promise<TaskStats> {
  const res = await request<ApiResponse<TaskStats>>("/analytics/tasks");
  return res.data;
}

export async function fetchIssueStats(): Promise<IssueStats> {
  const res = await request<ApiResponse<IssueStats>>("/analytics/issues");
  return res.data;
}
