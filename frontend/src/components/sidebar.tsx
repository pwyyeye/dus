"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "概览", icon: "📊" },
  { href: "/devices", label: "设备仪表盘", icon: "📈" },
  { href: "/machines", label: "设备管理", icon: "🖥️" },
  { href: "/tasks", label: "任务管理", icon: "📋" },
  { href: "/projects", label: "项目管理", icon: "📁" },
];

async function handleLogout() {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 border-r bg-muted/40 flex flex-col">
      <div className="p-4 border-b">
        <h1 className="text-lg font-bold tracking-tight">DUS 调度系统</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          分布式AI终端统一调度
        </p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
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
              <span>{item.label}</span>
            </Link>
          );
        })}
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
