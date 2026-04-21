"use client";

import { useRouter } from "next/navigation";
import { Task } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "..." : str;
}

interface TaskCardProps {
  task: Task;
}

export function TaskCard({ task }: TaskCardProps) {
  const router = useRouter();

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-sm font-mono">{task.task_id}</CardTitle>
            <p className="text-xs text-muted-foreground">
              创建: {formatTime(task.created_at)}
            </p>
          </div>
          <StatusBadge status={task.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm line-clamp-2">{truncate(task.instruction, 100)}</p>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          {task.started_at && (
            <span>开始: {formatTime(task.started_at)}</span>
          )}
          {task.completed_at && (
            <span>完成: {formatTime(task.completed_at)}</span>
          )}
        </div>

        {task.error_message && (
          <p className="text-xs text-destructive">错误: {truncate(task.error_message, 60)}</p>
        )}

        <div className="flex gap-2 pt-2">
          <Button size="sm" variant="outline" className="flex-1" onClick={() => router.push(`/tasks/${task.id}`)}>
            查看详情
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
