"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchTasks, fetchMachines, fetchUnassignedTasks, claimTask, cancelTask, Task, Machine } from "@/lib/api";
import { TaskCreateModal } from "@/components/task-create-modal";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PlusIcon, EyeIcon, XIcon, HandIcon } from "lucide-react";

type StatusFilter = "all" | "pending" | "running" | "completed" | "failed" | "unassigned";

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "pending", label: "待处理" },
  { value: "unassigned", label: "未分配" },
  { value: "running", label: "运行中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
];

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "..." : str;
}

function canCancel(status: string): boolean {
  return ["pending", "dispatched", "running"].includes(status);
}

export default function TasksPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks", statusFilter],
    queryFn: () => {
      if (statusFilter === "unassigned") return fetchUnassignedTasks();
      return fetchTasks(statusFilter === "all" ? undefined : { status: statusFilter });
    },
    refetchInterval: 5000,
  });

  const { data: machines } = useQuery({
    queryKey: ["machines"],
    queryFn: fetchMachines,
  });

  const cancelMutation = useMutation({
    mutationFn: cancelTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const claimMutation = useMutation({
    mutationFn: ({ taskId, machineId }: { taskId: string; machineId: string }) =>
      claimTask(taskId, machineId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["unassigned"] });
    },
  });

  const getMachineName = (machineId: string | null): string => {
    if (!machineId) return "-";
    const machine = machines?.find((m: Machine) => m.id === machineId);
    return machine?.machine_name ?? machineId.slice(0, 8);
  };

  const filteredTasks = tasks ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">任务管理</h2>
          <p className="text-muted-foreground">查看和管理所有任务</p>
        </div>
        <TaskCreateModal
          trigger={
            <Button>
              <PlusIcon className="size-4 mr-1" />
              新建任务
            </Button>
          }
        />
      </div>

      <Tabs value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
        <TabsList>
          {STATUS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="py-8 text-center text-muted-foreground">加载中...</div>
          ) : filteredTasks.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              暂无{statusFilter === "all" ? "" : STATUS_TABS.find((t) => t.value === statusFilter)?.label}任务
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务ID</TableHead>
                  <TableHead>指令</TableHead>
                  <TableHead>目标设备</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTasks.map((task: Task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-mono text-xs">{task.task_id}</TableCell>
                    <TableCell>
                      <div className="max-w-[300px]">
                        {task.status === "pending_manual" ? (
                          <div>
                            <p className="text-sm line-clamp-2">{truncate(task.instruction, 50)}</p>
                            <p className="text-xs text-amber-600 mt-1">
                              提醒已发送，请登录手动执行
                            </p>
                          </div>
                        ) : (
                          <p className="text-sm line-clamp-2">{truncate(task.instruction, 50)}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.target_machine_id
                        ? getMachineName(task.target_machine_id)
                        : <span className="text-amber-600 font-medium">未分配</span>}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={task.status} />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTime(task.created_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {statusFilter === "unassigned" && task.status === "pending" && !task.target_machine_id && (
                          <ClaimDropdown
                            machines={machines || []}
                            onClaim={(machineId) =>
                              claimMutation.mutate({ taskId: task.id, machineId })
                            }
                            disabled={claimMutation.isPending}
                          />
                        )}
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={() => router.push(`/tasks/${task.id}`)}
                          title="查看详情"
                        >
                          <EyeIcon className="size-3.5" />
                        </Button>
                        {canCancel(task.status) && (
                          <Button
                            size="icon-xs"
                            variant="ghost"
                            onClick={() => cancelMutation.mutate(task.id)}
                            disabled={cancelMutation.isPending}
                            title="取消任务"
                          >
                            <XIcon className="size-3.5" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ClaimDropdown({
  machines,
  onClaim,
  disabled,
}: {
  machines: Machine[];
  onClaim: (machineId: string) => void;
  disabled: boolean;
}) {
  const onlineMachines = machines.filter((m) => m.status === "online");

  if (onlineMachines.length === 0) return null;

  if (onlineMachines.length === 1) {
    return (
      <Button
        size="icon-xs"
        variant="ghost"
        onClick={() => onClaim(onlineMachines[0].id)}
        disabled={disabled}
        title="认领任务"
      >
        <HandIcon className="size-3.5" />
      </Button>
    );
  }

  return (
    <div className="relative group">
      <Button size="icon-xs" variant="ghost" title="认领任务" disabled={disabled}>
        <HandIcon className="size-3.5" />
      </Button>
      <div className="absolute left-0 top-full z-50 hidden min-w-[160px] rounded-md border bg-popover p-1 shadow-md group-hover:block">
        {onlineMachines.map((m) => (
          <button
            key={m.id}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
            onClick={() => onClaim(m.id)}
            disabled={disabled}
          >
            <HandIcon className="size-3" />
            {m.machine_name}
          </button>
        ))}
      </div>
    </div>
  );
}