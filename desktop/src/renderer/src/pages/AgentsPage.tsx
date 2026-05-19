import { useEffect, useState, useCallback } from "react";
import { fetchAgents, fetchMachines, fetchSkills, createAgent, updateAgent, deleteAgent, type Agent, type Machine, type Skill } from "../lib/api";
import { RefreshCw, Plus, Pencil, Trash2, Loader2 } from "lucide-react";

const categoryIcons: Record<string, string> = {
  coding: "💻",
  research: "🔍",
  data: "📊",
  web: "🌐",
  other: "📦",
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [agentsData, machinesData, skillsData] = await Promise.all([
        fetchAgents(),
        fetchMachines(),
        fetchSkills(),
      ]);
      setAgents(agentsData);
      setMachines(machinesData);
      setSkills(skillsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleCreate = async (data: { name: string; machine_id: string; description?: string; instructions?: string; model?: string; max_concurrent_tasks?: number }) => {
    try {
      await createAgent(data);
      setShowForm(false);
      loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建失败");
    }
  };

  const handleUpdate = async (id: string, data: Parameters<typeof updateAgent>[1]) => {
    try {
      await updateAgent(id, data);
      setEditing(null);
      loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "更新失败");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确认删除此智能体？")) return;
    try {
      await deleteAgent(id);
      loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-lg font-semibold">智能体管理</h1>
        <div className="flex items-center gap-2">
          <button onClick={loadData} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
            <RefreshCw size={14} />刷新
          </button>
          <button onClick={() => setShowForm(true)} className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs text-[var(--primary-foreground)] hover:opacity-90">
            <Plus size={14} />新建
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {error && (
          <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        {loading && agents.length === 0 ? (
          <div className="flex items-center justify-center py-12"><Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} /></div>
        ) : agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-[var(--muted-foreground)]">
            <p className="text-sm">暂无智能体，点击右上角新建</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="pb-2 pr-4 font-medium">名称</th>
                  <th className="pb-2 pr-4 font-medium">绑定设备</th>
                  <th className="pb-2 pr-4 font-medium">模型</th>
                  <th className="pb-2 pr-4 font-medium">技能</th>
                  <th className="pb-2 pr-4 font-medium">并发上限</th>
                  <th className="pb-2 pr-4 font-medium">状态</th>
                  <th className="pb-2 pr-4 font-medium">创建时间</th>
                  <th className="pb-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <tr key={a.id} className="border-b border-[var(--border)]/50 hover:bg-[var(--muted)]/30">
                    <td className="py-2.5 pr-4">
                      <div className="space-y-0.5">
                        <p className="font-medium text-sm">{a.name}</p>
                        {a.description && <p className="text-xs text-[var(--muted-foreground)] truncate max-w-xs">{a.description}</p>}
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 text-xs">
                      {a.machine?.machine_name ?? a.machine_id.slice(0, 8)}
                    </td>
                    <td className="py-2.5 pr-4 text-xs font-mono text-[var(--muted-foreground)]">
                      {a.model || "默认"}
                    </td>
                    <td className="py-2.5 pr-4">
                      <div className="flex flex-wrap gap-1">
                        {a.skills?.length ? (
                          a.skills.map((s) => (
                            <span key={s.id} className="inline-flex items-center rounded border border-[var(--border)] px-1.5 py-0.5 text-xs">
                              {categoryIcons[s.category ?? "other"] ?? "📦"} {s.name}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-[var(--muted-foreground)]">-</span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 text-xs">{a.max_concurrent_tasks}</td>
                    <td className="py-2.5 pr-4">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${a.is_enabled ? "bg-green-500/15 text-green-400" : "bg-gray-500/15 text-gray-400"}`}>
                        {a.is_enabled ? "启用" : "禁用"}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-xs text-[var(--muted-foreground)]">{formatTime(a.created_at)}</td>
                    <td className="py-2.5">
                      <div className="flex gap-1">
                        <button onClick={() => setEditing(a.id)} className="rounded p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)]" title="编辑">
                          <Pencil size={14} />
                        </button>
                        <button onClick={() => handleDelete(a.id)} className="rounded p-1 text-[var(--muted-foreground)] hover:bg-red-500/15 hover:text-red-400" title="删除">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showForm && (
        <SimpleAgentForm machines={machines} skills={skills} onSave={handleCreate} onClose={() => setShowForm(false)} />
      )}

      {editing && (
        <EditAgentForm agent={agents.find(a => a.id === editing)!} machines={machines} skills={skills} onSave={(data) => editing && handleUpdate(editing, data)} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

function SimpleAgentForm({ machines, skills, onSave, onClose }: {
  machines: Machine[]; skills: Skill[];
  onSave: (data: { name: string; machine_id: string; description?: string; instructions?: string; model?: string; max_concurrent_tasks?: number }) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [machineId, setMachineId] = useState(machines[0]?.id ?? "");
  const [desc, setDesc] = useState("");
  const [model, setModel] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !machineId) return;
    onSave({ name: name.trim(), machine_id: machineId, description: desc || undefined, model: model || undefined });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-96 rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl">
        <h2 className="mb-4 text-base font-semibold">新建智能体</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">名称 *</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="例: 安全审计专家" required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">绑定设备 *</label>
            <select value={machineId} onChange={e => setMachineId(e.target.value)} required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]">
              {machines.map(m => <option key={m.id} value={m.id}>{m.machine_name}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">描述</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2} placeholder="智能体用途说明..."
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">模型</label>
            <input value={model} onChange={e => setModel(e.target.value)} placeholder="默认使用设备模型"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-md px-4 py-2 text-sm text-[var(--muted-foreground)] hover:bg-[var(--muted)]">取消</button>
            <button type="submit" className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] hover:opacity-90">创建</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditAgentForm({ agent, machines, skills, onSave, onClose }: {
  agent: Agent; machines: Machine[]; skills: Skill[];
  onSave: (data: Parameters<typeof updateAgent>[1]) => void; onClose: () => void;
}) {
  const [name, setName] = useState(agent.name);
  const [desc, setDesc] = useState(agent.description ?? "");
  const [model, setModel] = useState(agent.model ?? "");
  const [enabled, setEnabled] = useState(agent.is_enabled);
  const [maxConcurrent, setMaxConcurrent] = useState(String(agent.max_concurrent_tasks));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      name: name.trim(),
      description: desc || undefined,
      model: model || undefined,
      is_enabled: enabled,
      max_concurrent_tasks: maxConcurrent ? parseInt(maxConcurrent, 10) : undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-96 rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl">
        <h2 className="mb-4 text-base font-semibold">编辑智能体</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">名称</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">描述</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">模型</label>
            <input value={model} onChange={e => setModel(e.target.value)}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">并发上限</label>
            <input type="number" value={maxConcurrent} onChange={e => setMaxConcurrent(e.target.value)} min="1"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="enabled" checked={enabled} onChange={e => setEnabled(e.target.checked)}
              className="rounded" />
            <label htmlFor="enabled" className="text-sm">启用智能体</label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-md px-4 py-2 text-sm text-[var(--muted-foreground)] hover:bg-[var(--muted)]">取消</button>
            <button type="submit" className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] hover:opacity-90">保存</button>
          </div>
        </form>
      </div>
    </div>
  );
}
