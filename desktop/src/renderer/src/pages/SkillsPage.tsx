import { useEffect, useState, useCallback } from "react";
import { fetchSkills, createSkill, deleteSkill, type Skill } from "../lib/api";
import { RefreshCw, Plus, Trash2, Loader2 } from "lucide-react";

const categoryConfig: Record<string, { label: string; icon: string; bg: string; text: string }> = {
  coding: { label: "编码", icon: "💻", bg: "bg-blue-500/15", text: "text-blue-400" },
  research: { label: "研究", icon: "🔍", bg: "bg-purple-500/15", text: "text-purple-400" },
  data: { label: "数据", icon: "📊", bg: "bg-green-500/15", text: "text-green-400" },
  web: { label: "Web", icon: "🌐", bg: "bg-orange-500/15", text: "text-orange-400" },
  other: { label: "其他", icon: "📦", bg: "bg-gray-500/15", text: "text-gray-400" },
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [showForm, setShowForm] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchSkills(categoryFilter ? { category: categoryFilter } : undefined);
      setSkills(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = async (data: { name: string; category?: string; description?: string }) => {
    try {
      await createSkill(data);
      setShowForm(false);
      loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建失败");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确认删除此技能？")) return;
    try {
      await deleteSkill(id);
      loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  };

  const categories = ["coding", "research", "data", "web", "other"];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-lg font-semibold">技能管理</h1>
        <div className="flex items-center gap-2">
          <button onClick={loadData} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
            <RefreshCw size={14} />刷新
          </button>
          <button onClick={() => setShowForm(true)} className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs text-[var(--primary-foreground)] hover:opacity-90">
            <Plus size={14} />新建
          </button>
        </div>
      </div>

      {/* Category filter */}
      <div className="flex gap-1 border-b border-[var(--border)] px-6 py-2">
        <button
          onClick={() => setCategoryFilter("")}
          className={`rounded-md px-3 py-1.5 text-xs transition-colors ${categoryFilter === "" ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]"}`}
        >
          全部
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={`rounded-md px-3 py-1.5 text-xs transition-colors ${categoryFilter === cat ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]"}`}
          >
            {categoryConfig[cat]?.icon} {categoryConfig[cat]?.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-6">
        {error && (
          <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        {loading && skills.length === 0 ? (
          <div className="flex items-center justify-center py-12"><Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} /></div>
        ) : skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-[var(--muted-foreground)]">
            <p className="text-sm">暂无技能，点击右上角新建</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {skills.map((skill) => {
              const cat = categoryConfig[skill.category ?? "other"] ?? categoryConfig.other;
              return (
                <div key={skill.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{cat.icon}</span>
                      <div>
                        <p className="font-medium text-sm">{skill.name}</p>
                        <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${cat.bg} ${cat.text}`}>
                          {cat.label}
                        </span>
                      </div>
                    </div>
                    <button onClick={() => handleDelete(skill.id)} className="rounded p-1 text-[var(--muted-foreground)] hover:bg-red-500/15 hover:text-red-400" title="删除">
                      <Trash2 size={14} />
                    </button>
                  </div>
                  {skill.description && (
                    <p className="mt-2 text-xs text-[var(--muted-foreground)] line-clamp-2">{skill.description}</p>
                  )}
                  <p className="mt-2 text-[10px] text-[var(--muted-foreground)]">{formatTime(skill.created_at)}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showForm && (
        <SkillForm onSave={handleCreate} onClose={() => setShowForm(false)} />
      )}
    </div>
  );
}

function SkillForm({ onSave, onClose }: {
  onSave: (data: { name: string; category?: string; description?: string }) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("coding");
  const [desc, setDesc] = useState("");

  const categories = [
    { value: "coding", label: "💻 编码" },
    { value: "research", label: "🔍 研究" },
    { value: "data", label: "📊 数据" },
    { value: "web", label: "🌐 Web" },
    { value: "other", label: "📦 其他" },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSave({ name: name.trim(), category, description: desc || undefined });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-96 rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl">
        <h2 className="mb-4 text-base font-semibold">新建技能</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">名称 *</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="例: Python Coding" required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">分类</label>
            <select value={category} onChange={e => setCategory(e.target.value)}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)]">
              {categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--muted-foreground)]">描述</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2} placeholder="技能详细描述..."
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
