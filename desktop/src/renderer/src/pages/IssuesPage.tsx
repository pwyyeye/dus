import { useEffect, useState, useCallback } from "react";
import { fetchIssues, type Issue } from "../lib/api";
import { RefreshCw, Loader2 } from "lucide-react";

const STATUS_TABS = [
  { value: "all", label: "全部" },
  { value: "todo", label: "待处理" },
  { value: "in_progress", label: "进行中" },
  { value: "done", label: "已完成" },
  { value: "cancelled", label: "已取消" },
];

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: "低", color: "text-[var(--muted-foreground)]" },
  medium: { label: "中", color: "text-blue-400" },
  high: { label: "高", color: "text-orange-400" },
  urgent: { label: "紧急", color: "text-red-400" },
};

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    todo: { bg: "bg-gray-500/15", text: "text-gray-400", label: "待处理" },
    in_progress: { bg: "bg-blue-500/15", text: "text-blue-400", label: "进行中" },
    done: { bg: "bg-green-500/15", text: "text-green-400", label: "已完成" },
    cancelled: { bg: "bg-gray-500/15", text: "text-gray-400", label: "已取消" },
  };
  const c = config[status] ?? config.todo;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

export default function IssuesPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setIssues(await fetchIssues(statusFilter === "all" ? undefined : { status: statusFilter }));
    } catch { /* error */ }
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-lg font-semibold">Issue 跟踪</h1>
        <button onClick={loadData} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
          <RefreshCw size={14} />刷新
        </button>
      </div>

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

      <div className="flex-1 overflow-auto p-6">
        {loading && issues.length === 0 ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} /></div>
        ) : issues.length === 0 ? (
          <div className="py-12 text-center text-sm text-[var(--muted-foreground)]">暂无 Issue</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                <th className="pb-2 pr-4 font-medium">ID</th>
                <th className="pb-2 pr-4 font-medium">标题</th>
                <th className="pb-2 pr-4 font-medium">优先级</th>
                <th className="pb-2 pr-4 font-medium">状态</th>
                <th className="pb-2 pr-4 font-medium">任务数</th>
                <th className="pb-2 font-medium">更新时间</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((issue) => (
                <tr key={issue.id} className="border-b border-[var(--border)]/50 hover:bg-[var(--muted)]/30">
                  <td className="py-2.5 pr-4 font-mono text-xs text-[var(--muted-foreground)]">{issue.issue_id.slice(0, 8)}</td>
                  <td className="max-w-sm py-2.5 pr-4">
                    <p className="truncate">{issue.title}</p>
                    {issue.description && (
                      <p className="mt-0.5 truncate text-xs text-[var(--muted-foreground)]">{issue.description}</p>
                    )}
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`text-xs font-medium ${PRIORITY_CONFIG[issue.priority]?.color ?? ""}`}>
                      {PRIORITY_CONFIG[issue.priority]?.label ?? issue.priority}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4"><StatusBadge status={issue.status} /></td>
                  <td className="py-2.5 pr-4 text-xs">{issue.task_count ?? 0}</td>
                  <td className="py-2.5 text-xs text-[var(--muted-foreground)]">{formatTime(issue.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
