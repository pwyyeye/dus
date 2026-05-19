import { useEffect, useState, useCallback } from "react";
import { fetchTasks, fetchMachines, cancelTask, type Task, type Machine } from "../lib/api";
import { RefreshCw, Eye, X, Plus, Loader2 } from "lucide-react";

const STATUS_TABS = [
  { value: "all", label: "全部" },
  { value: "pending", label: "待调度" },
  { value: "running", label: "执行中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
];

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    pending: { bg: "bg-yellow-500/15", text: "text-yellow-400", label: "待调度" },
    dispatched: { bg: "bg-blue-500/15", text: "text-blue-400", label: "已分发" },
    running: { bg: "bg-blue-500/15", text: "text-blue-400", label: "执行中" },
    completed: { bg: "bg-green-500/15", text: "text-green-400", label: "已完成" },
    failed: { bg: "bg-red-500/15", text: "text-red-400", label: "失败" },
    cancelled: { bg: "bg-gray-500/15", text: "text-gray-400", label: "已取消" },
    pending_manual: { bg: "bg-orange-500/15", text: "text-orange-400", label: "待人工" },
  };
  const c = config[status] ?? config.pending;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

export default function TasksPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tasksData, machinesData] = await Promise.all([
        fetchTasks(statusFilter === "all" ? undefined : { status: statusFilter }),
        fetchMachines(),
      ]);
      setTasks(tasksData);
      setMachines(machinesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const getMachineName = (id: string | null) => {
    if (!id) return "-";
    const m = machines.find((m) => m.id === id);
    return m?.machine_name ?? id.slice(0, 8);
  };

  const handleCancel = async (taskId: string) => {
    try {
      await cancelTask(taskId);
      loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "取消失败");
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-lg font-semibold">任务管理</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          >
            <RefreshCw size={14} />
            刷新
          </button>
        </div>
      </div>

      {/* Status tabs */}
      <div className="flex gap-1 border-b border-[var(--border)] px-6 py-2">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`rounded-md px-3 py-1.5 text-xs transition-colors ${
              statusFilter === tab.value
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {error && (
          <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {loading && tasks.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} />
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-[var(--muted-foreground)]">
            <p className="text-sm">暂无任务</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="pb-2 pr-4 font-medium">ID</th>
                  <th className="pb-2 pr-4 font-medium">指令</th>
                  <th className="pb-2 pr-4 font-medium">机器</th>
                  <th className="pb-2 pr-4 font-medium">状态</th>
                  <th className="pb-2 pr-4 font-medium">创建时间</th>
                  <th className="pb-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id} className="border-b border-[var(--border)]/50 hover:bg-[var(--muted)]/30">
                    <td className="py-2.5 pr-4">
                      <span className="font-mono text-xs text-[var(--muted-foreground)]">
                        {task.task_id.slice(0, 8)}
                      </span>
                    </td>
                    <td className="max-w-xs py-2.5 pr-4">
                      <p className="truncate text-sm">{truncate(task.instruction, 60)}</p>
                    </td>
                    <td className="py-2.5 pr-4 text-xs">
                      {task.target_machine_id ? (
                        <span>{getMachineName(task.target_machine_id)}</span>
                      ) : (
                        <span className="text-yellow-500">未分配</span>
                      )}
                    </td>
                    <td className="py-2.5 pr-4">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="py-2.5 pr-4 text-xs text-[var(--muted-foreground)]">
                      {formatTime(task.created_at)}
                    </td>
                    <td className="py-2.5">
                      <div className="flex gap-1">
                        {["pending", "dispatched", "running"].includes(task.status) && (
                          <button
                            onClick={() => handleCancel(task.id)}
                            className="rounded p-1 text-[var(--muted-foreground)] hover:bg-red-500/15 hover:text-red-400"
                            title="取消任务"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
