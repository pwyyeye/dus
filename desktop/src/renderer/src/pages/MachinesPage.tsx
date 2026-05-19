import { useEffect, useState, useCallback } from "react";
import { fetchMachines, type Machine } from "../lib/api";
import { RefreshCw, Loader2, Cpu } from "lucide-react";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function StatusBadge({ online }: { online: boolean }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
      online ? "bg-green-500/15 text-green-400" : "bg-gray-500/15 text-gray-400"
    }`}>
      {online ? "在线" : "离线"}
    </span>
  );
}

function AgentBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    idle: { bg: "bg-gray-500/15", text: "text-gray-400", label: "空闲" },
    busy: { bg: "bg-blue-500/15", text: "text-blue-400", label: "忙碌" },
    offline: { bg: "bg-gray-500/15", text: "text-gray-400", label: "离线" },
  };
  const c = config[status] ?? config.offline;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

export default function MachinesPage() {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setMachines(await fetchMachines());
    } catch { /* handled below */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const online = machines.filter((m) => m.status === "online").length;
  const idle = machines.filter((m) => m.agent_status === "idle").length;
  const busy = machines.filter((m) => m.agent_status === "busy").length;

  const stats = [
    { label: "在线机器", value: `${online}/${machines.length}` },
    { label: "空闲", value: idle },
    { label: "忙碌", value: busy },
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-lg font-semibold">机器管理</h1>
        <button onClick={loadData} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
          <RefreshCw size={14} />刷新
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 px-6 py-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="text-xs text-[var(--muted-foreground)]">{s.label}</div>
            <div className="mt-1 text-2xl font-bold">{loading ? "..." : s.value}</div>
          </div>
        ))}
      </div>

      <div className="flex-1 overflow-auto px-6 pb-6">
        {loading && machines.length === 0 ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} /></div>
        ) : machines.length === 0 ? (
          <div className="py-12 text-center text-sm text-[var(--muted-foreground)]">暂无机器注册</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                <th className="pb-2 pr-4 font-medium">机器ID</th>
                <th className="pb-2 pr-4 font-medium">名称</th>
                <th className="pb-2 pr-4 font-medium">类型</th>
                <th className="pb-2 pr-4 font-medium">在线</th>
                <th className="pb-2 pr-4 font-medium">Agent状态</th>
                <th className="pb-2 pr-4 font-medium">版本</th>
                <th className="pb-2 font-medium">最后轮询</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((m) => (
                <tr key={m.id} className="border-b border-[var(--border)]/50 hover:bg-[var(--muted)]/30">
                  <td className="py-2.5 pr-4 font-mono text-xs text-[var(--muted-foreground)]">{m.machine_id.slice(0, 8)}</td>
                  <td className="py-2.5 pr-4">{m.machine_name}</td>
                  <td className="py-2.5 pr-4">
                    <span className="flex flex-wrap gap-1">
                      {(m.available_agents ?? []).map((a) => (
                        <span key={a.cli_id || a.agent_type} className="rounded border border-[var(--border)] px-1.5 py-0.5 text-xs">
                          {a.agent_type}
                        </span>
                      ))}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4"><StatusBadge online={m.status === "online"} /></td>
                  <td className="py-2.5 pr-4"><AgentBadge status={m.agent_status} /></td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-[var(--muted-foreground)]">{m.agent_version || "-"}</td>
                  <td className="py-2.5 text-xs text-[var(--muted-foreground)]">{formatTime(m.last_poll_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
