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
  agent_version?: string;
  status: "online" | "offline";
  is_enabled: boolean;
  last_poll_at: string | null;
  registered_at: string;
  pending_task_count?: number;
}

export interface MachineDashboard {
  id: string;
  machine_id: string;
  machine_name: string;
  agent_type: string;
  agent_capability: string;
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
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: Record<string, unknown>;
  error_message: string | null;
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
}): Promise<Task> {
  const res = await request<ApiResponse<Task>>("/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
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

// ── Project API ──

export async function fetchProjects(): Promise<Project[]> {
  const res = await request<ApiResponse<Project[]>>("/projects");
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
