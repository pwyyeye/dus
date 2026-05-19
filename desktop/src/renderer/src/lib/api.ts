// Desktop API client - mirrors frontend/src/lib/api.ts but without Next.js SSR

let _apiBase = "http://localhost:8000/api/v1";
let _apiKey = "";

export function configureApi(baseUrl: string, apiKey: string) {
  _apiBase = baseUrl.replace(/\/+$/, "");
  _apiKey = apiKey;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...((options.headers as Record<string, string>) || {}),
    };
    if (_apiKey) headers["X-API-Key"] = _apiKey;

    const res = await fetch(`${_apiBase}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!res.ok) {
      let detail = `API Error: ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch { /* not json */ }
      throw new Error(detail);
    }

    return res.json();
  } catch (err) {
    clearTimeout(timeout);
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Request timeout after 30s");
    }
    throw err;
  }
}

// --- Types ---

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta?: Record<string, unknown>;
}

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
  task_count?: number;
  tasks?: Task[];
  sub_issues?: Issue[];
  labels?: Label[];
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
  issue_count?: number;
}

export interface Label {
  id: string;
  name: string;
  color: string | null;
  created_at: string;
}

export interface Autopilot {
  id: string;
  name: string;
  description: string | null;
  project_id: string | null;
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

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  agent_type: string;
  status: string;
  machine_id: string;
  instructions: string | null;
  model: string | null;
  bound_cli_id: string | null;
  bound_cli_type: string | null;
  max_concurrent_tasks: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
  machine?: Machine | null;
  skills: Skill[];
}

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  config: Record<string, unknown> | null;
  created_at: string;
}

// --- API Functions ---

export async function fetchMachines(): Promise<Machine[]> {
  const res = await request<ApiResponse<Machine[]>>("/machines");
  return res.data;
}

export async function fetchMachinesDashboard(): Promise<MachineDashboard[]> {
  const res = await request<ApiResponse<MachineDashboard[]>>("/machines/dashboard");
  return res.data;
}

export async function fetchTasks(params?: { status?: string }): Promise<Task[]> {
  const qs = params?.status ? `?status=${params.status}` : "";
  const res = await request<ApiResponse<Task[]>>(`/tasks${qs}`);
  return res.data;
}

export async function fetchUnassignedTasks(): Promise<Task[]> {
  const res = await request<ApiResponse<Task[]>>("/tasks?status=pending&unassigned=true");
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
  issue_id?: string;
}): Promise<Task> {
  const res = await request<ApiResponse<Task>>("/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function cancelTask(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/tasks/${id}/cancel`, { method: "POST" });
}

export async function claimTask(taskId: string, machineId: string): Promise<void> {
  await request<ApiResponse<void>>(`/tasks/${taskId}/claim`, {
    method: "POST",
    body: JSON.stringify({ machine_id: machineId }),
  });
}

export async function fetchIssues(params?: {
  status?: string;
  project_id?: string;
  label_id?: string;
  sort?: string;
}): Promise<Issue[]> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== "all") query.set("status", params.status);
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.label_id) query.set("label_id", params.label_id);
  if (params?.sort) query.set("sort", params.sort);
  const qs = query.toString();
  const res = await request<ApiResponse<Issue[]>>(`/issues${qs ? `?${qs}` : ""}`);
  return res.data;
}

export async function fetchIssue(id: string): Promise<Issue> {
  const res = await request<ApiResponse<Issue>>(`/issues/${id}`);
  return res.data;
}

export async function createIssue(data: {
  title: string;
  description?: string;
  project_id?: string;
  priority?: string;
  assignee_type?: string;
  assignee_id?: string;
  label_ids?: string[];
  agent_cli_id?: string;
}): Promise<Issue> {
  const res = await request<ApiResponse<Issue>>("/issues", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateIssue(id: string, data: Partial<{
  title: string;
  description: string;
  status: string;
  priority: string;
  assignee_type: string;
  assignee_id: string;
  label_ids: string[];
  agent_cli_id: string;
  project_id: string;
}>): Promise<Issue> {
  const res = await request<ApiResponse<Issue>>(`/issues/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await request<ApiResponse<Project[]>>("/projects");
  return res.data;
}

export async function fetchAgents(params?: { machine_id?: string; is_enabled?: boolean }): Promise<Agent[]> {
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

export async function fetchSkills(params?: { category?: string }): Promise<Skill[]> {
  const query = new URLSearchParams();
  if (params?.category) query.set("category", params.category);
  const qs = query.toString();
  const res = await request<ApiResponse<Skill[]>>(`/skills${qs ? `?${qs}` : ""}`);
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

export async function deleteSkill(id: string): Promise<void> {
  await request<ApiResponse<void>>(`/skills/${id}`, { method: "DELETE" });
}

export async function fetchLabels(): Promise<Label[]> {
  const res = await request<ApiResponse<Label[]>>("/labels");
  return res.data;
}

export async function fetchAutopilots(): Promise<Autopilot[]> {
  const res = await request<ApiResponse<Autopilot[]>>("/autopilots");
  return res.data;
}

export async function fetchInboxItems(params?: {
  is_read?: boolean;
  limit?: number;
  offset?: number;
}): Promise<{ items: InboxItem[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.is_read !== undefined) query.set("is_read", String(params.is_read));
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
