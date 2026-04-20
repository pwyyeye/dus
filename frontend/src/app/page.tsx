"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchMachinesDashboard, updateMachine, createTask, MachineDashboard } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "destructive" | "outline" | "secondary";

const statusMap: Record<string, { label: string; variant: BadgeVariant }> = {
  pending: { label: "待处理", variant: "outline" },
  dispatched: { label: "已分派", variant: "secondary" },
  running: { label: "运行中", variant: "default" },
  completed: { label: "已完成", variant: "default" },
  failed: { label: "失败", variant: "destructive" },
  cancelled: { label: "已取消", variant: "secondary" },
  pending_manual: { label: "待手动", variant: "outline" },
};

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "..." : str;
}

function MachineCard({ machine }: { machine: MachineDashboard }) {
  const [dispatchOpen, setDispatchOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const queryClient = useQueryClient();

  const isOnline = machine.status === "online";
  const isEnabled = machine.is_enabled;
  const isBusy = machine.running_tasks.length > 0;

  const updateMutation = useMutation({
    mutationFn: (data: { is_enabled?: boolean }) => updateMachine(machine.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["machines-dashboard"] });
    },
  });

  const dispatchMutation = useMutation({
    mutationFn: (data: { instruction: string }) =>
      createTask({
        instruction: data.instruction,
        target_machine_id: machine.id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["machines-dashboard"] });
      setDispatchOpen(false);
      setInstruction("");
    },
  });

  const onDispatch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!instruction.trim()) return;
    dispatchMutation.mutate({ instruction });
  };

  return (
    <Card className={cn("relative", !isEnabled && "opacity-60")}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base">{machine.machine_name}</CardTitle>
            <CardDescription className="font-mono text-xs">
              {machine.machine_id}
            </CardDescription>
          </div>
          <div className="flex flex-col gap-1 items-end">
            <Badge variant={isOnline ? "default" : "secondary"}>
              {isOnline ? "在线" : "离线"}
            </Badge>
            <Badge variant={isEnabled ? "outline" : "destructive"}>
              {isEnabled ? "可用" : "禁用"}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-2">
          <Badge variant={isBusy ? "default" : "outline"}>
            {isBusy ? `执行中 (${machine.running_tasks.length})` : "空闲"}
          </Badge>
          <Badge variant="outline">{machine.agent_type}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Running Tasks */}
        {machine.running_tasks.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">运行中任务</p>
            {machine.running_tasks.map((task) => (
              <div key={task.id} className="rounded-md border p-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium truncate">{truncate(task.instruction, 40)}</span>
                  <Badge variant="secondary" className="ml-2 shrink-0">
                    {task.status === "running" ? "运行" : "分派"}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{task.task_id}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground text-center py-2">暂无运行中任务</p>
        )}

        {/* Quick Stats */}
        <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-3">
          <span>今日完成: {machine.completed_tasks_count}</span>
          <span>最后心跳: {formatTime(machine.last_poll_at)}</span>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => updateMutation.mutate({ is_enabled: !isEnabled })}
            disabled={updateMutation.isPending}
          >
            {isEnabled ? "禁用" : "启用"}
          </Button>
          <Dialog open={dispatchOpen} onOpenChange={setDispatchOpen}>
            <DialogTrigger render={<Button size="sm" className="flex-1" disabled={!isEnabled || !isOnline} />}>
              下发任务
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle>向 {machine.machine_name} 下发任务</DialogTitle>
              </DialogHeader>
              <form onSubmit={onDispatch} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="dispatch-instruction">执行指令</Label>
                  <Textarea
                    id="dispatch-instruction"
                    placeholder="描述 Agent 需要执行的指令..."
                    rows={5}
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    required
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setDispatchOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={dispatchMutation.isPending}>
                    {dispatchMutation.isPending ? "下发中..." : "下发"}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: machines, isLoading } = useQuery({
    queryKey: ["machines-dashboard"],
    queryFn: fetchMachinesDashboard,
  });

  const onlineCount = machines?.filter((m) => m.status === "online").length ?? 0;
  const totalMachines = machines?.length ?? 0;
  const enabledCount = machines?.filter((m) => m.is_enabled).length ?? 0;
  const busyCount = machines?.filter((m) => m.running_tasks.length > 0).length ?? 0;
  const totalRunningTasks = machines?.reduce((acc, m) => acc + m.running_tasks.length, 0) ?? 0;
  const totalCompletedToday = machines?.reduce((acc, m) => acc + m.completed_tasks_count, 0) ?? 0;

  const stats = [
    { title: "在线设备", value: `${onlineCount} / ${totalMachines}`, desc: "当前在线 / 总注册" },
    { title: "可用设备", value: `${enabledCount} / ${totalMachines}`, desc: "已启用设备" },
    { title: "忙碌设备", value: busyCount, desc: "正在执行任务" },
    { title: "执行中任务", value: totalRunningTasks, desc: "已分派或运行中" },
    { title: "今日完成", value: totalCompletedToday, desc: "任务完成数" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">设备概览</h2>
        <p className="text-muted-foreground">查看所有设备状态并快速下发任务</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {stats.map((s) => (
          <Card key={s.title}>
            <CardHeader className="pb-2">
              <CardDescription>{s.desc}</CardDescription>
              <CardTitle className="text-sm font-medium">{s.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {isLoading ? "..." : s.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Device Cards */}
      <div>
        <h3 className="text-lg font-semibold mb-4">设备列表</h3>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">加载中...</p>
        ) : !machines?.length ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              暂无注册设备
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {machines.map((machine) => (
              <MachineCard key={machine.id} machine={machine} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
