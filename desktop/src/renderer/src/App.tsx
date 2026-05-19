import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  Cpu,
  ListTodo,
  AlertCircle,
  FolderKanban,
  BarChart3,
  Inbox,
  Zap,
  Play,
  Square,
  RotateCw,
  ChevronLeft,
  ChevronRight,
  Terminal,
  Bot,
  Crosshair,
} from "lucide-react";
import TasksPage from "./pages/TasksPage";
import MachinesPage from "./pages/MachinesPage";
import IssuesPage from "./pages/IssuesPage";
import ProjectsPage from "./pages/ProjectsPage";
import InboxPage from "./pages/InboxPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import AutopilotsPage from "./pages/AutopilotsPage";
import AgentsPage from "./pages/AgentsPage";
import SkillsPage from "./pages/SkillsPage";

interface BridgeStatus {
  state: string;
  pid?: number;
  agents?: string[];
  activeTaskCount?: number;
}

type Page = "tasks" | "machines" | "issues" | "projects" | "analytics" | "inbox" | "autopilots" | "agents" | "skills";

const NAV_ITEMS: { id: Page; label: string; icon: React.ReactNode }[] = [
  { id: "inbox", label: "收件箱", icon: <Inbox size={16} /> },
  { id: "issues", label: "Issue", icon: <AlertCircle size={16} /> },
  { id: "projects", label: "项目", icon: <FolderKanban size={16} /> },
  { id: "agents", label: "智能体", icon: <Bot size={16} /> },
  { id: "autopilots", label: "自动化", icon: <Zap size={16} /> },
  { id: "machines", label: "机器", icon: <Cpu size={16} /> },
  { id: "tasks", label: "任务", icon: <ListTodo size={16} /> },
  { id: "skills", label: "技能", icon: <Crosshair size={16} /> },
  { id: "analytics", label: "统计", icon: <BarChart3 size={16} /> },
];

function Sidebar({ page, setPage, collapsed }: { page: Page; setPage: (p: Page) => void; collapsed: boolean }) {
  return (
    <nav className="flex flex-col gap-0.5 py-2">
      {NAV_ITEMS.map((item) => (
        <button key={item.id} onClick={() => setPage(item.id)}
          className={`flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-[13px] transition-colors ${
            page === item.id
              ? "bg-[var(--sidebar-accent)] text-[var(--sidebar-accent-foreground)]"
              : "text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)]/50 hover:text-[var(--foreground)]"
          }`} title={collapsed ? item.label : undefined}>
          {item.icon}
          {!collapsed && <span>{item.label}</span>}
        </button>
      ))}
    </nav>
  );
}

function BridgeStatusFooter({ status, onAction, collapsed }: { status: BridgeStatus; onAction: (a: string) => void; collapsed: boolean }) {
  const isRunning = status.state === "running";
  const stateColor = isRunning ? "bg-[var(--success)]"
    : status.state === "starting" ? "bg-[var(--warning)] animate-pulse"
    : status.state === "error" ? "bg-[var(--destructive)]"
    : "bg-[var(--muted-foreground)]";

  if (collapsed) return (
    <div className="flex flex-col items-center gap-1 py-2">
      <span className={`h-2 w-2 rounded-full ${stateColor}`} />
      <button onClick={() => onAction(isRunning ? "stop" : "start")} className="rounded p-1 text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)]">
        {isRunning ? <Square size={12} /> : <Play size={12} />}
      </button>
    </div>
  );

  return (
    <div className="px-3 py-3">
      <div className="rounded-lg border border-[var(--sidebar-border)] bg-[var(--sidebar-accent)]/50 p-2.5">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-[var(--muted-foreground)]" />
          <span className="text-xs font-medium">Bridge</span>
          <span className={`ml-auto h-2 w-2 rounded-full ${stateColor}`} />
        </div>
        <p className="mt-1 text-[11px] text-[var(--muted-foreground)]">
          {isRunning ? `${status.activeTaskCount ?? 0} 任务 • ${status.agents?.length ?? 0} Agent`
            : status.state === "starting" ? "启动中..."
            : status.state === "error" ? "启动失败" : "已停止"}
        </p>
        <div className="mt-2 flex gap-1">
          <button onClick={() => onAction(isRunning ? "stop" : "start")}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--foreground)] transition-colors">
            {isRunning ? <Square size={10} /> : <Play size={10} />}
            {isRunning ? "停止" : "启动"}
          </button>
          <button onClick={() => onAction("restart")}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--foreground)] transition-colors">
            <RotateCw size={10} />重启
          </button>
        </div>
      </div>
    </div>
  );
}

function LogViewer({ lines, onClose }: { lines: string[]; onClose: () => void }) {
  const ref = useState<HTMLDivElement | null>(null);
  useEffect(() => { if (ref[0]) ref[0].scrollTop = ref[0].scrollHeight; }, [ref[0], lines.length]);
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-2">
        <span className="text-xs font-medium">Bridge 日志</span>
        <button onClick={onClose} className="rounded p-0.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
          <span className="text-xs">✕</span>
        </button>
      </div>
      <div ref={(el) => ref[1](el)} className="flex-1 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed">
        {lines.length === 0 ? <div className="text-[var(--muted-foreground)]">等待日志...</div>
          : lines.map((l, i) => <div key={i} className="whitespace-pre-wrap text-[var(--muted-foreground)]">{l}</div>)}
      </div>
    </div>
  );
}

function PageContent({ page }: { page: Page }) {
  switch (page) {
    case "tasks": return <TasksPage />;
    case "machines": return <MachinesPage />;
    case "issues": return <IssuesPage />;
    case "projects": return <ProjectsPage />;
    case "inbox": return <InboxPage />;
    case "analytics": return <AnalyticsPage />;
    case "autopilots": return <AutopilotsPage />;
    case "agents": return <AgentsPage />;
    case "skills": return <SkillsPage />;
    default: return <TasksPage />;
  }
}

export default function App() {
  const [page, setPage] = useState<Page>("tasks");
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>({ state: "stopped" });
  const [logLines, setLogLines] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    window.bridgeAPI.getStatus().then(setBridgeStatus);
    window.bridgeAPI.autoStart();
    return window.bridgeAPI.onStatusChange(setBridgeStatus);
  }, []);

  useEffect(() => {
    return window.bridgeAPI.onLogLine((line) => {
      setLogLines((prev) => {
        const next = [...prev, line];
        return next.length > 500 ? next.slice(-500) : next;
      });
    });
  }, []);

  const handleBridgeAction = useCallback(async (action: string) => {
    if (action === "start") await window.bridgeAPI.start();
    else if (action === "stop") await window.bridgeAPI.stop();
    else await window.bridgeAPI.restart();
  }, []);

  const sbw = sidebarCollapsed ? 48 : 200;

  return (
    <div className="flex h-screen bg-[var(--background)]">
      <aside className="flex shrink-0 flex-col border-r border-[var(--sidebar-border)] bg-[var(--sidebar)]" style={{ width: sbw }}>
        <div className="drag-region flex h-12 shrink-0 items-center px-3">
          {!sidebarCollapsed && <span className="text-sm font-semibold tracking-tight">DUS</span>}
        </div>
        <div className="flex-1 overflow-y-auto px-2">
          <Sidebar page={page} setPage={setPage} collapsed={sidebarCollapsed} />
        </div>
        <BridgeStatusFooter status={bridgeStatus} onAction={handleBridgeAction} collapsed={sidebarCollapsed} />
        <div className="border-t border-[var(--sidebar-border)] p-1.5">
          <button onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="flex w-full items-center justify-center rounded-md p-1 text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--foreground)] transition-colors">
            {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="drag-region flex h-12 shrink-0 items-center gap-2 px-4">
          <div className="ml-auto flex items-center gap-2" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
            <button onClick={() => setShowLogs(!showLogs)}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] transition-colors ${
                showLogs ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
              }`}>
              <Activity size={12} />日志
              {logLines.length > 0 && <span className="rounded bg-[var(--muted)] px-1 py-0.5 text-[10px]">{logLines.length}</span>}
            </button>
          </div>
        </header>

        <div className="relative mr-2 mb-2 ml-0.5 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl shadow-sm bg-[var(--background)]">
          <div className="flex-1 overflow-auto">
            <PageContent page={page} />
          </div>
          {showLogs && (
            <div className="h-48 shrink-0 border-t border-[var(--border)]">
              <LogViewer lines={logLines} onClose={() => setShowLogs(false)} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
