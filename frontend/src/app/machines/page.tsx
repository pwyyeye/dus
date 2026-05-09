"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { fetchMachines, fetchAgents, Machine } from "@/lib/api";
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
import { ChevronDownIcon, ChevronRightIcon, EyeIcon } from "lucide-react";
import { SkeletonTable } from "@/components/ui/skeleton";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function MachineRow({ machine }: { machine: Machine }) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  const { data: agents, isFetching } = useQuery({
    queryKey: ["agents", machine.id],
    queryFn: () => fetchAgents({ machine_id: machine.id }),
    enabled: expanded,
  });

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={() => setExpanded(!expanded)}
      >
        <TableCell className="font-mono text-xs">
          {machine.machine_id}
        </TableCell>
        <TableCell>{machine.machine_name}</TableCell>
        <TableCell>
          <Badge variant="outline">{machine.agent_type}</Badge>
        </TableCell>
        <TableCell>
          <Badge
            variant={
              machine.agent_capability === "remote_execution"
                ? "default"
                : "secondary"
            }
          >
            {machine.agent_capability === "remote_execution"
              ? "远程执行"
              : "手动"}
          </Badge>
        </TableCell>
        <TableCell>
          <Badge
            variant={
              machine.status === "online" ? "default" : "destructive"
            }
          >
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
            {machine.agent_status === "busy"
              ? "运行中"
              : machine.agent_status === "idle"
                ? "闲置"
                : "离线"}
          </Badge>
        </TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">
          {machine.agent_version || "-"}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {formatTime(machine.last_poll_at)}
        </TableCell>
        <TableCell>
          {expanded ? (
            <ChevronDownIcon className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRightIcon className="size-4 text-muted-foreground" />
          )}
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-muted/30">
          <TableCell colSpan={9} className="p-0">
            <div className="px-6 py-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">
                绑定智能体
              </p>
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
                        <TableCell className="text-xs font-mono text-muted-foreground">
                          {a.model || "默认"}
                        </TableCell>
                        <TableCell className="text-xs">{a.max_concurrent_tasks}</TableCell>
                        <TableCell>
                          <Badge variant={a.is_enabled ? "default" : "secondary"} className="text-xs">
                            {a.is_enabled ? "启用" : "禁用"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button
                            size="icon-xs"
                            variant="ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              router.push(`/agents/${a.id}`);
                            }}
                            title="查看智能体"
                          >
                            <EyeIcon className="size-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
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