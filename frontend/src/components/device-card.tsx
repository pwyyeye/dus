"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateMachine, createTask, Machine } from "@/lib/api";
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

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "..." : str;
}

interface DeviceCardProps {
  machine: Machine;
  runningTasks?: Array<{
    id: string;
    task_id: string;
    instruction: string;
    status: string;
  }>;
  className?: string;
}

export function DeviceCard({ machine, runningTasks = [], className }: DeviceCardProps) {
  const [dispatchOpen, setDispatchOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const queryClient = useQueryClient();

  const isOnline = machine.status === "online";
  const isEnabled = machine.is_enabled;
  const isBusy = runningTasks.length > 0;

  const updateMutation = useMutation({
    mutationFn: (data: { is_enabled?: boolean }) => updateMachine(machine.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["machines"] });
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
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
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
    <Card className={cn("relative", !isEnabled && "opacity-60", className)}>
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
            {isBusy ? `执行中 (${runningTasks.length})` : "空闲"}
          </Badge>
          <Badge variant="outline">{machine.agent_type}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {runningTasks.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">运行中任务</p>
            {runningTasks.map((task) => (
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

        <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-3">
          <span>待处理: {machine.pending_task_count ?? 0}</span>
          <span>最后心跳: {formatTime(machine.last_poll_at)}</span>
        </div>

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
                  <Label htmlFor={`dispatch-instruction-${machine.id}`}>执行指令</Label>
                  <Textarea
                    id={`dispatch-instruction-${machine.id}`}
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
