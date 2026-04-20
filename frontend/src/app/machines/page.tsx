"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchMachines } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
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
        <p className="text-muted-foreground">查看所有注册设备及其状态</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>设备列表</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">加载中...</p>
          ) : !machines?.length ? (
            <p className="text-sm text-muted-foreground">暂无注册设备</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>设备ID</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>Agent 类型</TableHead>
                  <TableHead>执行能力</TableHead>
                  <TableHead>在线状态</TableHead>
                  <TableHead>可用性</TableHead>
                  <TableHead>最后心跳</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {machines.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-mono text-xs">
                      {m.machine_id}
                    </TableCell>
                    <TableCell>{m.machine_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{m.agent_type}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          m.agent_capability === "remote_execution"
                            ? "default"
                            : "secondary"
                        }
                      >
                        {m.agent_capability === "remote_execution"
                          ? "远程执行"
                          : "手动"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          m.status === "online" ? "default" : "destructive"
                        }
                      >
                        {m.status === "online" ? "在线" : "离线"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={m.is_enabled ? "outline" : "destructive"}
                      >
                        {m.is_enabled ? "可用" : "禁用"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTime(m.last_poll_at)}
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
