"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { fetchUnreadCount } from "@/lib/api";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  badge?: number;
}

interface NavGroup {
  title?: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    items: [
      { href: "/inbox", label: "收件箱", icon: "🔔" },
    ],
  },
  {
    title: "工作区",
    items: [
      { href: "/issues", label: "Issue 管理", icon: "🎫" },
      { href: "/kanban", label: "看板", icon: "📌" },
      { href: "/projects", label: "项目管理", icon: "📁" },
      { href: "/agents", label: "智能体", icon: "🤖" },
      { href: "/autopilots", label: "定时任务", icon: "⏰" },
    ],
  },
  {
    title: "配置",
    items: [
      { href: "/machines", label: "设备管理", icon: "🖥️" },
      { href: "/devices", label: "设备仪表盘", icon: "📈" },
      { href: "/tasks", label: "任务管理", icon: "📋" },
      { href: "/skills", label: "技能管理", icon: "🎯" },
      { href: "/analytics", label: "使用量分析", icon: "📉" },
    ],
  },
];

async function handleLogout() {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
}

export function Sidebar() {
  const pathname = usePathname();

  const { data: unreadCount } = useQuery({
    queryKey: ["inbox-unread"],
    queryFn: fetchUnreadCount,
    refetchInterval: 30000,
  });

  const groups = navGroups.map((g) => ({
    ...g,
    items: g.items.map((item) =>
      item.href === "/inbox" && unreadCount
        ? { ...item, badge: unreadCount }
        : item
    ),
  }));

  return (
    <aside className="w-60 border-r bg-muted/40 flex flex-col">
      <Link href="/tasks" className="block p-4 border-b hover:bg-muted/50 transition-colors">
        <h1 className="text-lg font-bold tracking-tight">DUS 调度系统</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          分布式AI终端统一调度
        </p>
      </Link>
      <nav className="flex-1 p-3 space-y-4 overflow-y-auto">
        {groups.map((group, gi) => (
          <div key={gi}>
            {group.title && (
              <p className="px-3 mb-1 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                {group.title}
              </p>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    )}
                  >
                    <span>{item.icon}</span>
                    <span className="flex-1">{item.label}</span>
                    {item.badge !== undefined && item.badge > 0 && (
                      <span
                        className={cn(
                          "min-w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-medium tabular-nums",
                          isActive
                            ? "bg-primary-foreground/20 text-primary-foreground"
                            : "bg-destructive text-destructive-foreground"
                        )}
                      >
                        {item.badge > 99 ? "99+" : item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="p-4 border-t flex items-center justify-between">
        <span className="text-xs text-muted-foreground">v1.0.0</span>
        <button
          onClick={handleLogout}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          退出
        </button>
      </div>
    </aside>
  );
}
