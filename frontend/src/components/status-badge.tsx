"use client";

import { Badge } from "@/components/ui/badge";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "ghost" | "link";

const statusConfig: Record<string, { label: string; variant: BadgeVariant }> = {
  // Task statuses
  pending: { label: "待处理", variant: "outline" },
  dispatched: { label: "已分派", variant: "secondary" },
  running: { label: "运行中", variant: "default" },
  completed: { label: "已完成", variant: "default" },
  failed: { label: "失败", variant: "destructive" },
  cancelled: { label: "已取消", variant: "secondary" },
  pending_manual: { label: "待手动", variant: "outline" },
  // Machine statuses
  online: { label: "在线", variant: "default" },
  offline: { label: "离线", variant: "secondary" },
  // Project statuses
  active: { label: "活跃", variant: "default" },
  archived: { label: "已归档", variant: "secondary" },
  idle: { label: "闲置", variant: "outline" },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status] ?? { label: status, variant: "outline" as BadgeVariant };
  return (
    <Badge variant={config.variant} className={className}>
      {config.label}
    </Badge>
  );
}
