"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { fetchTask, fetchMachines, fetchProjects, updateTask, cancelTask, Machine, Project } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function canCancel(status: string): boolean {
  return ["pending", "dispatched", "running"].includes(status);
}

function canMarkComplete(status: string): boolean {
  return status === "pending_manual";
}

function RunningAnimation() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex space-x-1">
        <span className="block w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="block w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="block w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
      <span className="text-sm text-blue-600">执行中...</span>
    </div>
  );
}

export default function TaskDetailPage() {
  const router = useRouter();
  const params = useParams();
  const queryClient = useQueryClient();
  const taskId = params.id as string;

  const { data: task, isLoading, error } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => fetchTask(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const task = query.state.data;
      // Poll every 3 seconds when task is running, otherwise don't poll
      if (task?.status === "running" || task?.status === "pending" || task?.status === "dispatched") {
        return 3000;
      }
      return false;
    },
  });

  const { data: machines } = useQuery({
    queryKey: ["machines"],
    queryFn: fetchMachines,
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateTask(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const getMachineName = (machineId: string | null): string => {
    if (!machineId) return "-";
    const machine = machines?.find((m: Machine) => m.id === machineId);
    return machine?.machine_name ?? machineId.slice(0, 8);
  };

  const getProjectName = (projectId: string | null): string => {
    if (!projectId) return "-";
    const project = projects?.find((p: Project) => p.id === projectId);
    return project?.project_name ?? projectId.slice(0, 8);
  };

  const result = task?.result as { stdout?: string; stderr?: string } | null;

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
        {/* Basic Info Card */}
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
                {task.status === "running" ? (
                  <RunningAnimation />
                ) : (
                  <StatusBadge status={task.status} />
                )}
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
              <div>
                <div className="text-muted-foreground">目标设备</div>
                <div>{getMachineName(task.target_machine_id)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">所属项目</div>
                <div>{getProjectName(task.project_id)}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Execution Instruction Card */}
        <Card>
          <CardHeader>
            <CardTitle>执行指令</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{task.instruction}</p>
          </CardContent>
        </Card>

        {/* Manual Task Reminder */}
        {task.status === "pending_manual" && (
          <Card className="md:col-span-2 border-amber-200 bg-amber-50/50">
            <CardHeader>
              <CardTitle className="text-amber-700"> 手动任务待执行</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-amber-700">
                提醒已发送至企业微信，请登录目标设备手动执行任务。
              </p>
              <p className="text-xs text-amber-600">
                执行完成后请点击下方「标记完成」按钮。
              </p>
            </CardContent>
          </Card>
        )}

        {/* Error Message */}
        {task.error_message && (
          <Card className="md:col-span-2 border-destructive/50 bg-destructive/5">
            <CardHeader>
              <CardTitle className="text-destructive">错误信息</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-destructive whitespace-pre-wrap">{task.error_message}</p>
            </CardContent>
          </Card>
        )}

        {/* Execution Result */}
        {(result?.stdout || result?.stderr) && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>执行结果</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {result.stdout && (
                <div>
                  <div className="text-sm font-medium mb-1">标准输出 (stdout)</div>
                  <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-64 font-mono">
                    {result.stdout}
                  </pre>
                </div>
              )}
              {result.stderr && (
                <div>
                  <div className="text-sm font-medium mb-1">标准错误 (stderr)</div>
                  <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-64 font-mono text-destructive">
                    {result.stderr}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Raw Result (if no stdout/stderr but has result) */}
        {!result?.stdout && !result?.stderr && task.result && Object.keys(task.result).length > 0 && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>执行结果</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto max-h-64">
                {JSON.stringify(task.result, null, 2)}
              </pre>
            </CardContent>
          </Card>
        )}

        {/* Action Buttons */}
        <Card className="md:col-span-2">
          <CardContent className="pt-6">
            <div className="flex gap-3 justify-end">
              {canCancel(task.status) && (
                <Button
                  variant="destructive"
                  onClick={() => cancelMutation.mutate(task.id)}
                  disabled={cancelMutation.isPending}
                >
                  取消任务
                </Button>
              )}
              {canMarkComplete(task.status) && (
                <Button
                  onClick={() => updateMutation.mutate({ id: task.id, status: "completed" })}
                  disabled={updateMutation.isPending}
                >
                  标记完成
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}