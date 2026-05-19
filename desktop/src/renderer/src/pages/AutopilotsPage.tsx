import { useEffect, useState, useCallback } from "react";
import { fetchAutopilots, type Autopilot } from "../lib/api";
import { RefreshCw, Loader2, Zap } from "lucide-react";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

export default function AutopilotsPage() {
  const [items, setItems] = useState<Autopilot[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try { setItems(await fetchAutopilots()); } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-lg font-semibold">自动化任务</h1>
        <button onClick={loadData} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
          <RefreshCw size={14} />刷新
        </button>
      </div>
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} /></div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-sm text-[var(--muted-foreground)]">暂无自动化任务</div>
        ) : (
          <div className="space-y-3">
            {items.map((a) => (
              <div key={a.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
                <div className="flex items-center gap-2">
                  <Zap size={16} className={a.is_enabled ? "text-yellow-400" : "text-[var(--muted-foreground)]"} />
                  <h3 className="font-medium">{a.name}</h3>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${a.is_enabled ? "bg-green-500/15 text-green-400" : "bg-gray-500/15 text-gray-400"}`}>
                    {a.is_enabled ? "启用" : "禁用"}
                  </span>
                </div>
                {a.description && <p className="mt-2 text-xs text-[var(--muted-foreground)]">{a.description}</p>}
                <div className="mt-3 flex items-center gap-4 text-xs text-[var(--muted-foreground)]">
                  <span>触发: {a.trigger_type}</span>
                  <span>运行次数: {a.run_count}</span>
                  <span>上次运行: {formatTime(a.last_run_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
