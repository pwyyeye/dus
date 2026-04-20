"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchTasks, fetchMachines, createTask } from "@/lib/api";
import {
  Card,
  CardContent,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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

export default function TasksPage() {
  const [open, setOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [targetMachineId, setTargetMachineId] = useState("");
  const queryClient = useQueryClient();

  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => fetchTasks(),
  });

  const { data: machines } = useQuery({
    queryKey: ["machines"],
    queryFn: fetchMachines,
  });

  const mutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setOpen(false);
      setInstruction("");
      setTargetMachineId("");
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!instruction.trim()) return;
    mutation.mutate({
      instruction,
      target_machine_id: targetMachineId || undefined,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">任务管理</h2>
          <p className="text-muted-foreground">查看和管理所有任务</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button />}>
            创建任务
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>创建新任务</DialogTitle>
            </DialogHeader>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="instruction">执行指令</Label>
                <Textarea
                  id="instruction"
                  placeholder="描述 Agent 需要执行的指令..."
                  rows={5}
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>目标设备</Label>
                <select
                  className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm"
                  value={targetMachineId}
                  onChange={(e) => setTargetMachineId(e.target.value)}
                >
                  <option value="">不指定设备</option>
                  {machines?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.machine_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? "创建中..." : "创建"}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务列表</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">加载中...</p>
          ) : !tasks?.length ? (
            <p className="text-sm text-muted-foreground">暂无任务，点击右上角创建</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务ID</TableHead>
                  <TableHead>指令</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((t) => {
                  const st = statusMap[t.status] ?? { label: t.status, variant: "outline" as BadgeVariant };
                  return (
                    <TableRow key={t.id}>
                      <TableCell className="font-mono text-xs">{t.task_id}</TableCell>
                      <TableCell className="font-medium">{truncate(t.instruction, 50)}</TableCell>
                      <TableCell>
                        <Badge variant={st.variant}>{st.label}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTime(t.created_at)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
