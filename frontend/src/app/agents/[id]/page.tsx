"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAgent, fetchAgentActivity, updateAgent, deleteAgent, ActivityDay } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeftIcon, TrashIcon, ActivityIcon, SettingsIcon, CodeIcon } from "lucide-react";
import { toast } from "sonner";

interface PageProps {
  params: Promise<{ id: string }>;
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

const categoryIcons: Record<string, string> = {
  coding: "💻",
  research: "🔍",
  data: "📊",
  web: "🌐",
  other: "📦",
};

function ActivitySparkline({ data }: { data: ActivityDay[] }) {
  if (!data || data.length === 0) return null;
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="flex items-end gap-px h-16">
      {data.map((day, i) => {
        const height = day.count > 0 ? Math.max((day.count / maxCount) * 100, 8) : 0;
        return (
          <div
            key={i}
            className="flex-1 flex items-end"
            title={`${day.date}: ${day.count} 个任务`}
          >
            <div
              className={`w-full rounded-t-sm transition-all ${
                day.count > 0 ? "bg-primary/80" : "bg-transparent"
              }`}
              style={{ height: `${height}%` }}
            />
          </div>
        );
      })}
    </div>
  );
}

function InspectorRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="text-sm">{children}</div>
    </div>
  );
}

export default function AgentDetailPage({ params }: PageProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { id } = React.use(params);

  const { data: agent, isLoading } = useQuery({
    queryKey: ["agent", id],
    queryFn: () => fetchAgent(id),
  });

  const { data: activity } = useQuery({
    queryKey: ["agent-activity", id],
    queryFn: () => fetchAgentActivity(id, 30),
  });

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => updateAgent(id, { is_enabled: enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent", id] });
      toast.success(agent?.is_enabled ? "智能体已禁用" : "智能体已启用");
    },
    onError: (err: Error) => toast.error(`操作失败: ${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAgent(id),
    onSuccess: () => {
      toast.success("智能体已删除");
      router.push("/agents");
    },
    onError: (err: Error) => toast.error(`删除失败: ${err.message}`),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex gap-6">
          <Skeleton className="w-80 h-[500px] shrink-0" />
          <div className="flex-1 space-y-4">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (!agent) {
    return <div className="text-center py-8 text-muted-foreground">智能体不存在或已删除</div>;
  }

  const totalTasks = activity?.reduce((sum, d) => sum + d.count, 0) ?? 0;

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <Button size="sm" variant="outline" onClick={() => router.push("/agents")}>
          <ArrowLeftIcon className="size-4 mr-1" />
          返回列表
        </Button>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => toggleMutation.mutate(!agent.is_enabled)}
            disabled={toggleMutation.isPending}
          >
            {agent.is_enabled ? "禁用" : "启用"}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => {
              if (confirm("确认删除此智能体？")) deleteMutation.mutate();
            }}
            disabled={deleteMutation.isPending}
          >
            <TrashIcon className="size-4 mr-1" />
            删除
          </Button>
        </div>
      </div>

      {/* Two-column Inspector layout */}
      <div className="flex gap-6 items-start">
        {/* Left: Inspector */}
        <div className="w-80 shrink-0 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg">{agent.name}</CardTitle>
                <Badge variant={agent.is_enabled ? "default" : "secondary"} className="text-xs">
                  {agent.is_enabled ? "启用" : "禁用"}
                </Badge>
              </div>
              {agent.description && (
                <CardDescription className="text-xs">{agent.description}</CardDescription>
              )}
            </CardHeader>
            <CardContent className="space-y-0">
              <InspectorRow label="绑定设备">
                <span className="font-medium">
                  {agent.machine?.machine_name ?? agent.machine_id.slice(0, 8)}
                </span>
              </InspectorRow>
              <InspectorRow label="设备类型">
                <span className="font-mono text-xs">{agent.machine?.agent_type ?? "-"}</span>
              </InspectorRow>
              <InspectorRow label="设备状态">
                <Badge
                  variant={agent.machine?.status === "online" ? "default" : "secondary"}
                  className="text-xs"
                >
                  {agent.machine?.status === "online" ? "在线" : "离线"}
                </Badge>
              </InspectorRow>
              <InspectorRow label="模型">
                <span className="font-mono text-xs">{agent.model || "默认"}</span>
              </InspectorRow>
              <InspectorRow label="并发上限">
                <span className="font-medium">{agent.max_concurrent_tasks}</span>
              </InspectorRow>
              <InspectorRow label="创建时间">
                <span className="text-xs">{formatTime(agent.created_at)}</span>
              </InspectorRow>
              <InspectorRow label="更新时间">
                <span className="text-xs">{formatTime(agent.updated_at)}</span>
              </InspectorRow>
            </CardContent>
          </Card>

          {/* Skills */}
          {agent.skills && agent.skills.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-1.5">
                  <CodeIcon className="size-3.5" />
                  技能
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {agent.skills.map((skill) => (
                    <Badge key={skill.id} variant="outline" className="text-xs">
                      {categoryIcons[skill.category ?? "other"] ?? "📦"} {skill.name}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Quick stats */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">30天任务总量</p>
                  <p className="text-2xl font-bold">{totalTasks}</p>
                </div>
                <ActivityIcon className="size-8 text-muted-foreground/30" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Content */}
        <div className="flex-1 space-y-4 min-w-0">
          {/* Activity Sparkline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ActivityIcon className="size-4" />
                活动统计
              </CardTitle>
              <CardDescription>过去 30 天的任务执行情况</CardDescription>
            </CardHeader>
            <CardContent>
              {activity && activity.length > 0 ? (
                <ActivitySparkline data={activity} />
              ) : (
                <p className="text-sm text-muted-foreground">暂无活动数据</p>
              )}
            </CardContent>
          </Card>

          {/* Instructions */}
          {agent.instructions && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <SettingsIcon className="size-4" />
                  系统指令
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-sm whitespace-pre-wrap font-sans bg-muted/50 rounded-md p-3 max-h-64 overflow-y-auto">
                  {agent.instructions}
                </pre>
              </CardContent>
            </Card>
          )}

          {/* Config section */}
          <div className="grid gap-4 sm:grid-cols-2">
            {agent.custom_env && Object.keys(agent.custom_env).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">自定义环境变量</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs font-mono whitespace-pre-wrap bg-muted/50 rounded-md p-3">
                    {JSON.stringify(agent.custom_env, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
            {agent.custom_args && agent.custom_args.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">自定义 CLI 参数</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs font-mono whitespace-pre-wrap bg-muted/50 rounded-md p-3">
                    {agent.custom_args.join(" ")}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>

          {agent.mcp_config && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">MCP 配置</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs font-mono whitespace-pre-wrap bg-muted/50 rounded-md p-3 max-h-48 overflow-y-auto">
                  {JSON.stringify(agent.mcp_config, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
