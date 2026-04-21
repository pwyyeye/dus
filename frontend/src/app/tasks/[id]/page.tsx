"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { fetchTask } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function formatJson(obj: Record<string, unknown> | null): string {
  if (!obj) return "-";
  return JSON.stringify(obj, null, 2);
}

export default function TaskDetailPage() {
  const router = useRouter();
  const params = useParams();
  const taskId = params.id as string;

  const { data: task, isLoading, error } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => fetchTask(taskId),
    enabled: !!taskId,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">任务详情</h2>
          <p className="text-muted-foreground">加载中...</p>
        </div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">任务详情</h2>
          <p className="text-destructive">任务不存在或加载失败</p>
        </div>
        <Button variant="outline" onClick={() => router.push("/tasks")}>
          返回任务列表
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">任务详情</h2>
          <p className="text-muted-foreground font-mono text-sm">{task.task_id}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={task.status} />
          <Button variant="outline" onClick={() => router.push("/tasks")}>
            返回列表
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>基本信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">任务ID</div>
                <div className="font-mono">{task.task_id}</div>
              </div>
              <div>
                <div className="text-muted-foreground">状态</div>
                <StatusBadge status={task.status} />
              </div>
              <div>
                <div className="text-muted-foreground">创建时间</div>
                <div>{formatTime(task.created_at)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">开始时间</div>
                <div>{formatTime(task.started_at)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">完成时间</div>
                <div>{formatTime(task.completed_at)}</div>
              </div>
              {task.project_id && (
                <div>
                  <div className="text-muted-foreground">项目ID</div>
                  <div className="font-mono text-xs">{task.project_id}</div>
                </div>
              )}
              {task.target_machine_id && (
                <div>
                  <div className="text-muted-foreground">目标设备</div>
                  <div className="font-mono text-xs">{task.target_machine_id}</div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>执行指令</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{task.instruction}</p>
          </CardContent>
        </Card>

        {task.error_message && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="text-destructive">错误信息</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-destructive whitespace-pre-wrap">{task.error_message}</p>
            </CardContent>
          </Card>
        )}

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>执行结果</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-64">
              {formatJson(task.result)}
            </pre>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
