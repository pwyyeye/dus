"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchIssue, fetchIssueTasks } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowLeftIcon, EyeIcon } from "lucide-react";

interface PageProps {
  params: Promise<{ id: string }>;
}

const priorityConfig: Record<string, { label: string; color: string }> = {
  low: { label: "低", color: "text-muted-foreground" },
  medium: { label: "中", color: "text-blue-600" },
  high: { label: "高", color: "text-orange-600" },
  urgent: { label: "紧急", color: "text-red-600" },
};

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "..." : str;
}

export default function IssueDetailPage({ params }: PageProps) {
  const router = useRouter();
  const { id } = React.use(params);

  const { data: issue, isLoading: issueLoading } = useQuery({
    queryKey: ["issue", id],
    queryFn: () => fetchIssue(id),
  });

  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["issue-tasks", id],
    queryFn: () => fetchIssueTasks(id),
    refetchInterval: 5000,
  });

  if (issueLoading) {
    return (
      <div className="space-y-6">
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      </div>
    );
  }

  if (!issue) {
    return (
      <div className="space-y-6">
        <div className="text-center py-8 text-muted-foreground">Issue 不存在或已删除</div>
      </div>
    );
  }

  const pConfig = priorityConfig[issue.priority] ?? { label: issue.priority, color: "" };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => router.push("/issues")}>
          <ArrowLeftIcon className="size-4 mr-1" />
          返回列表
        </Button>
      </div>

      <div>
        <h2 className="text-2xl font-bold tracking-tight">{issue.title}</h2>
        <p className="text-muted-foreground font-mono text-xs mt-1">{issue.issue_id}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>状态</CardDescription>
          </CardHeader>
          <CardContent>
            <StatusBadge status={issue.status} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>优先级</CardDescription>
          </CardHeader>
          <CardContent>
            <span className={`font-medium ${pConfig.color}`}>{pConfig.label}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>执行次数</CardDescription>
          </CardHeader>
          <CardContent>
            <span className="font-medium">{tasks?.length ?? 0}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>更新时间</CardDescription>
          </CardHeader>
          <CardContent>
            <span className="text-sm">{formatTime(issue.updated_at)}</span>
          </CardContent>
        </Card>
      </div>

      {issue.description && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">描述</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{issue.description}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">执行历史</CardTitle>
          <CardDescription>该 Issue 关联的所有任务执行记录</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {tasksLoading ? (
            <div className="py-8 text-center text-muted-foreground">加载中...</div>
          ) : !tasks || tasks.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">暂无执行记录</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务ID</TableHead>
                  <TableHead>指令</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>目标设备</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-mono text-xs">{task.task_id}</TableCell>
                    <TableCell>
                      <p className="text-sm line-clamp-2 max-w-[300px]">
                        {truncate(task.instruction, 60)}
                      </p>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={task.status} />
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.target_machine_id ? task.target_machine_id.slice(0, 8) : "-"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTime(task.created_at)}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        onClick={() => router.push(`/tasks/${task.id}`)}
                        title="查看任务详情"
                      >
                        <EyeIcon className="size-3.5" />
                      </Button>
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
