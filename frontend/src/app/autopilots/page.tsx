"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchAutopilots,
  createAutopilot,
  deleteAutopilot,
  triggerAutopilot,
  updateAutopilot,
  Autopilot,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  PlusIcon,
  PlayIcon,
  TrashIcon,
  RefreshCwIcon,
} from "lucide-react";
import { toast } from "sonner";
import { SkeletonTable } from "@/components/ui/skeleton";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

const triggerTypeConfig: Record<string, { label: string; color: string }> = {
  cron: { label: "Cron", color: "bg-blue-100 text-blue-700" },
  interval: { label: "间隔", color: "bg-green-100 text-green-700" },
  webhook: { label: "Webhook", color: "bg-purple-100 text-purple-700" },
  manual: { label: "手动", color: "bg-gray-100 text-gray-700" },
};

export default function AutopilotsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data: autopilots, isLoading } = useQuery({
    queryKey: ["autopilots"],
    queryFn: () => fetchAutopilots(),
    refetchInterval: 30000,
  });

  const createMut = useMutation({
    mutationFn: createAutopilot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["autopilots"] });
      setOpen(false);
      toast.success("定时任务创建成功");
    },
    onError: (err: Error) => toast.error(`创建失败: ${err.message}`),
  });

  const deleteMut = useMutation({
    mutationFn: deleteAutopilot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["autopilots"] });
      toast.success("定时任务已删除");
    },
    onError: (err: Error) => toast.error(`删除失败: ${err.message}`),
  });

  const triggerMut = useMutation({
    mutationFn: triggerAutopilot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["autopilots"] });
      toast.success("任务已触发");
    },
    onError: (err: Error) => toast.error(`触发失败: ${err.message}`),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      updateAutopilot(id, { is_enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["autopilots"] });
      toast.success("状态已更新");
    },
    onError: (err: Error) => toast.error(`更新失败: ${err.message}`),
  });

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const name = fd.get("name") as string;
    const description = fd.get("description") as string;
    const triggerType = fd.get("trigger_type") as string;
    const intervalMinutes = fd.get("interval_minutes") as string;
    const cronExpr = fd.get("cron_expr") as string;

    if (!name.trim()) return;

    createMut.mutate({
      name,
      description: description || undefined,
      trigger_type: triggerType,
      interval_minutes: intervalMinutes ? parseInt(intervalMinutes) : undefined,
      cron_expr: cronExpr || undefined,
    });
    form.reset();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">定时任务</h2>
          <p className="text-muted-foreground">管理自动化任务调度</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <PlusIcon className="size-4 mr-1" />
          新建定时任务
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <SkeletonTable rows={5} cols={6} />
          ) : !autopilots || autopilots.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              暂无定时任务
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>触发方式</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>上次运行</TableHead>
                  <TableHead>下次运行</TableHead>
                  <TableHead>运行次数</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {autopilots.map((ap: Autopilot) => {
                  const config = triggerTypeConfig[ap.trigger_type] ?? {
                    label: ap.trigger_type,
                    color: "bg-gray-100 text-gray-700",
                  };
                  return (
                    <TableRow key={ap.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium text-sm">{ap.name}</p>
                          {ap.description && (
                            <p className="text-xs text-muted-foreground line-clamp-1">
                              {ap.description}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={config.color}>
                          {config.label}
                          {ap.trigger_type === "interval" &&
                            ap.interval_minutes &&
                            ` (${ap.interval_minutes}m)`}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={ap.is_enabled ? "default" : "secondary"}
                        >
                          {ap.is_enabled ? "启用" : "禁用"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTime(ap.last_run_at)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTime(ap.next_run_at)}
                      </TableCell>
                      <TableCell className="text-sm">{ap.run_count}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            size="icon-xs"
                            variant="ghost"
                            title="立即执行"
                            onClick={() => triggerMut.mutate(ap.id)}
                            disabled={!ap.is_enabled || triggerMut.isPending}
                          >
                            <PlayIcon className="size-3.5" />
                          </Button>
                          <Button
                            size="icon-xs"
                            variant="ghost"
                            title={ap.is_enabled ? "禁用" : "启用"}
                            onClick={() =>
                              toggleMut.mutate({
                                id: ap.id,
                                is_enabled: !ap.is_enabled,
                              })
                            }
                          >
                            <RefreshCwIcon className="size-3.5" />
                          </Button>
                          <Button
                            size="icon-xs"
                            variant="ghost"
                            className="text-destructive"
                            title="删除"
                            onClick={() => deleteMut.mutate(ap.id)}
                          >
                            <TrashIcon className="size-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>新建定时任务</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ap-name">名称</Label>
              <Input
                id="ap-name"
                name="name"
                placeholder="任务名称..."
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ap-desc">描述</Label>
              <Textarea
                id="ap-desc"
                name="description"
                placeholder="任务描述或执行指令..."
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ap-trigger">触发方式</Label>
              <Select name="trigger_type" defaultValue="interval">
                <SelectTrigger id="ap-trigger">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="interval">间隔触发</SelectItem>
                  <SelectItem value="cron">Cron 表达式</SelectItem>
                  <SelectItem value="webhook">Webhook</SelectItem>
                  <SelectItem value="manual">手动触发</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ap-interval">间隔（分钟）</Label>
              <Input
                id="ap-interval"
                name="interval_minutes"
                type="number"
                min="1"
                placeholder="60"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ap-cron">Cron 表达式</Label>
              <Input
                id="ap-cron"
                name="cron_expr"
                placeholder="0 9 * * 1-5"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                取消
              </Button>
              <Button type="submit" disabled={createMut.isPending}>
                {createMut.isPending ? "创建中..." : "创建"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
