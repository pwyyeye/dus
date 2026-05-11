"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { fetchMachines, fetchAgents, createTask, Machine } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ChevronDownIcon, ChevronRightIcon, EyeIcon } from "lucide-react";
import { SkeletonTable } from "@/components/ui/skeleton";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function MachineRow({ machine }: { machine: Machine }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [dispatchOpen, setDispatchOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [selectedAgentCli, setSelectedAgentCli] = useState("");

  const { data: agents, isFetching } = useQuery({
    queryKey: ["agents", machine.id],
    queryFn: () => fetchAgents({ machine_id: machine.id }),
    enabled: expanded,
  });

  const dispatchMutation = useMutation({
    mutationFn: (data: { instruction: string; agent_cli_id?: string }) =>
      createTask({
        instruction: data.instruction,
        target_machine_id: machine.id,
        agent_cli_id: data.agent_cli_id || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setDispatchOpen(false);
      setInstruction("");
      setSelectedAgentCli("");
    },
  });

  const availableAgents = machine.available_agents ?? [];

  const onDispatch = (e: React.FormEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (!instruction.trim()) return;
    dispatchMutation.mutate({ instruction, agent_cli_id: selectedAgentCli || undefined });
  };

  return (
    <>
      <TableRow className="hover:bg-muted/50">
        <TableCell className="font-mono text-xs">{machine.machine_id}</TableCell>
        <TableCell>{machine.machine_name}</TableCell>
        <TableCell>
          <div className="flex flex-wrap gap-1">
            {availableAgents.map((a) => (
              <Badge key={a.cli_id || a.agent_type} variant="outline" className="text-xs">
                {a.agent_type}
              </Badge>
            ))}
          </div>
        </TableCell>
        <TableCell>
          <Badge
            variant={
              machine.agent_capability === "remote_execution" ? "default" : "secondary"
            }
          >
            {machine.agent_capability === "remote_execution" ? "远程执行" : "手动"}
          </Badge>
        </TableCell>
        <TableCell>
          <Badge variant={machine.status === "online" ? "default" : "destructive"}>
            {machine.status === "online" ? "在线" : "离线"}
          </Badge>
        </TableCell>
        <TableCell>
          <Badge
            variant={
              machine.agent_status === "busy"
                ? "default"
                : machine.agent_status === "idle"
                  ? "outline"
                  : "secondary"
            }
          >
            {machine.agent_status === "busy" ? "运行中" : machine.agent_status === "idle" ? "闲置" : "离线"}
          </Badge>
        </TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">
          {machine.agent_version || "-"}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {formatTime(machine.last_poll_at)}
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-1">
            {machine.status === "online" && machine.agent_capability === "remote_execution" && (
              <Dialog open={dispatchOpen} onOpenChange={(open) => { setDispatchOpen(open); }}>
                <DialogTrigger render={<Button size="icon-xs" variant="ghost" onClick={(e) => e.stopPropagation()}>
                    <span title="下发任务">▶</span>
                  </Button>} />
                <DialogContent onClick={(e) => e.stopPropagation()}>
                  <DialogHeader>
                    <DialogTitle>向 {machine.machine_name} 下发任务</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={onDispatch} className="space-y-4">
                    {availableAgents.length > 1 && (
                      <div className="space-y-2">
                        <Label>选择 Agent CLI</Label>
                        <Select value={selectedAgentCli} onValueChange={(v) => setSelectedAgentCli(v || "")}>
                          <SelectTrigger>
                            <SelectValue>
                              {selectedAgentCli
                                ? (() => { const a = availableAgents.find(x => (x.cli_id || x.agent_type) === selectedAgentCli); return a ? `${a.agent_type} v${a.version}` : selectedAgentCli; })()
                                : "默认（第一个可用）"}
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent>
                            {availableAgents.map((a) => (
                              <SelectItem key={a.cli_id || a.agent_type} value={a.cli_id || a.agent_type}>
                                {a.agent_type} <span className="text-muted-foreground text-xs ml-1">v{a.version}</span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    <div className="space-y-2">
                      <Label htmlFor={`inst-${machine.id}`}>执行指令</Label>
                      <Textarea
                        id={`inst-${machine.id}`}
                        rows={5}
                        value={instruction}
                        onChange={(e) => setInstruction(e.target.value)}
                        placeholder="描述 Agent 需要执行的指令..."
                        required
                      />
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button type="button" variant="outline" onClick={() => setDispatchOpen(false)}>取消</Button>
                      <Button type="submit" disabled={dispatchMutation.isPending}>
                        {dispatchMutation.isPending ? "下发中..." : "下发"}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            )}
            <Button size="icon-xs" variant="ghost" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
            </Button>
          </div>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-muted/30">
          <TableCell colSpan={9} className="p-0">
            <div className="px-6 py-3 space-y-3">
              {availableAgents.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-2">可用 Agent CLI</p>
                  <div className="flex flex-wrap gap-2">
                    {availableAgents.map((a) => (
                      <Badge key={a.cli_id || a.agent_type} variant="secondary" className="text-xs">
                        {a.agent_type} <span className="ml-1 text-muted-foreground">v{a.version}</span>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">绑定智能体</p>
                {isFetching ? (
                  <p className="text-xs text-muted-foreground">加载中...</p>
                ) : !agents?.length ? (
                  <p className="text-xs text-muted-foreground">暂无，请前往智能体页面创建</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">名称</TableHead>
                        <TableHead className="text-xs">模型</TableHead>
                        <TableHead className="text-xs">并发</TableHead>
                        <TableHead className="text-xs">状态</TableHead>
                        <TableHead className="text-xs">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {agents.map((a) => (
                        <TableRow key={a.id}>
                          <TableCell className="text-sm">{a.name}</TableCell>
                          <TableCell className="text-xs font-mono text-muted-foreground">{a.model || "默认"}</TableCell>
                          <TableCell className="text-xs">{a.max_concurrent_tasks}</TableCell>
                          <TableCell>
                            <Badge variant={a.is_enabled ? "default" : "secondary"} className="text-xs">
                              {a.is_enabled ? "启用" : "禁用"}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Button size="icon-xs" variant="ghost" onClick={() => router.push(`/agents/${a.id}`)} title="查看智能体">
                              <EyeIcon className="size-3.5" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export default function MachinesPage() {
  const { data: machines, isLoading } = useQuery({
    queryKey: ["machines"],
    queryFn: fetchMachines,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">设备管理</h2>
        <p className="text-muted-foreground">查看所有注册设备及其状态（点击展开查看智能体）</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>设备列表</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <SkeletonTable rows={5} cols={6} />
          ) : !machines?.length ? (
            <p className="text-sm text-muted-foreground py-8 text-center">暂无注册设备</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>设备ID</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>Agent 类型</TableHead>
                  <TableHead>执行能力</TableHead>
                  <TableHead>在线状态</TableHead>
                  <TableHead>负载状态</TableHead>
                  <TableHead>Bridge 版本</TableHead>
                  <TableHead>最后心跳</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {machines.map((m) => (
                  <MachineRow key={m.id} machine={m} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}