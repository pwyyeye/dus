import { useEffect, useState, useCallback } from "react";
import { fetchProjects, type Project } from "../lib/api";
import { RefreshCw, Loader2 } from "lucide-react";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try { setProjects(await fetchProjects()); } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-lg font-semibold">项目管理</h1>
        <button onClick={loadData} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
          <RefreshCw size={14} />刷新
        </button>
      </div>
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-[var(--muted-foreground)]" size={24} /></div>
        ) : projects.length === 0 ? (
          <div className="py-12 text-center text-sm text-[var(--muted-foreground)]">暂无项目</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <div key={p.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
                <h3 className="font-medium">{p.project_name}</h3>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">{p.root_path || "-"}</p>
                <div className="mt-3 flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
                  <span>{p.issue_count ?? 0} Issue</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
