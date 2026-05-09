"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchAnalyticsOverview,
  fetchTaskStats,
  fetchIssueStats,
  AnalyticsOverview,
  TaskStats,
  IssueStats,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BarChart3Icon,
  CheckCircleIcon,
  ClipboardListIcon,
  TicketIcon,
  MonitorIcon,
  BotIcon,
  FolderIcon,
} from "lucide-react";

function MiniBarChart({
  data,
  maxItems = 7,
}: {
  data: { date: string; count: number }[];
  maxItems?: number;
}) {
  const slice = data.slice(-maxItems);
  const max = Math.max(...slice.map((d) => d.count), 1);
  return (
    <div className="flex items-end gap-1 h-24">
      {slice.map((d) => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-0.5">
          <span className="text-[10px] text-muted-foreground">{d.count}</span>
          <div
            className="w-full bg-primary/80 rounded-t"
            style={{ height: `${(d.count / max) * 100}%`, minHeight: d.count > 0 ? 4 : 0 }}
          />
          <span className="text-[10px] text-muted-foreground">
            {d.date.slice(5)}
          </span>
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    todo: "bg-gray-100 text-gray-700",
    in_progress: "bg-blue-100 text-blue-700",
    done: "bg-green-100 text-green-700",
    completed: "bg-green-100 text-green-700",
    cancelled: "bg-red-100 text-red-700",
    failed: "bg-red-100 text-red-700",
    pending: "bg-yellow-100 text-yellow-700",
    running: "bg-blue-100 text-blue-700",
    dispatched: "bg-purple-100 text-purple-700",
    low: "bg-gray-100 text-gray-600",
    medium: "bg-yellow-100 text-yellow-700",
    high: "bg-orange-100 text-orange-700",
    urgent: "bg-red-100 text-red-700",
  };
  return (
    <Badge variant="secondary" className={`text-xs ${colors[status] ?? ""}`}>
      {status}
    </Badge>
  );
}

function DistributionList({
  distribution,
}: {
  distribution: Record<string, number>;
}) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="space-y-2">
      {Object.entries(distribution).map(([key, count]) => (
        <div key={key} className="flex items-center gap-2">
          <StatusBadge status={key} />
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary/60 rounded-full"
              style={{ width: `${(count / total) * 100}%` }}
            />
          </div>
          <span className="text-sm text-muted-foreground w-8 text-right">
            {count}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: fetchAnalyticsOverview,
  });

  const { data: taskStats, isLoading: taskLoading } = useQuery({
    queryKey: ["analytics", "tasks"],
    queryFn: fetchTaskStats,
  });

  const { data: issueStats, isLoading: issueLoading } = useQuery({
    queryKey: ["analytics", "issues"],
    queryFn: fetchIssueStats,
  });

  const isLoading = overviewLoading || taskLoading || issueLoading;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <BarChart3Icon className="size-6" />
          使用量分析
        </h2>
        <p className="text-muted-foreground">系统运行数据统计</p>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-muted-foreground">加载中...</div>
      ) : (
        <>
          {/* Overview Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <ClipboardListIcon className="size-5 mx-auto mb-1 text-muted-foreground" />
                <p className="text-2xl font-bold">{overview?.counts.tasks ?? 0}</p>
                <p className="text-xs text-muted-foreground">总任务</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <TicketIcon className="size-5 mx-auto mb-1 text-muted-foreground" />
                <p className="text-2xl font-bold">{overview?.counts.issues ?? 0}</p>
                <p className="text-xs text-muted-foreground">总 Issue</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <MonitorIcon className="size-5 mx-auto mb-1 text-muted-foreground" />
                <p className="text-2xl font-bold">{overview?.counts.machines ?? 0}</p>
                <p className="text-xs text-muted-foreground">设备</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <BotIcon className="size-5 mx-auto mb-1 text-muted-foreground" />
                <p className="text-2xl font-bold">{overview?.counts.agents ?? 0}</p>
                <p className="text-xs text-muted-foreground">智能体</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <FolderIcon className="size-5 mx-auto mb-1 text-muted-foreground" />
                <p className="text-2xl font-bold">{overview?.counts.projects ?? 0}</p>
                <p className="text-xs text-muted-foreground">项目</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <CheckCircleIcon className="size-5 mx-auto mb-1 text-muted-foreground" />
                <p className="text-2xl font-bold">
                  {overview?.task_success_rate ?? 0}%
                </p>
                <p className="text-xs text-muted-foreground">任务成功率</p>
              </CardContent>
            </Card>
          </div>

          {/* Recent Activity */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <div className="text-3xl font-bold text-primary">
                  {overview?.recent.tasks_7d ?? 0}
                </div>
                <div>
                  <p className="text-sm font-medium">近 7 天新任务</p>
                  <p className="text-xs text-muted-foreground">
                    在线设备 {overview?.online_machines ?? 0} 台
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <div className="text-3xl font-bold text-primary">
                  {overview?.recent.issues_7d ?? 0}
                </div>
                <div>
                  <p className="text-sm font-medium">近 7 天新 Issue</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Task Stats */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">任务状态分布</CardTitle>
              </CardHeader>
              <CardContent>
                {taskStats?.status_distribution ? (
                  <DistributionList distribution={taskStats.status_distribution} />
                ) : (
                  <p className="text-muted-foreground text-sm">暂无数据</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">任务创建趋势 (近 30 天)</CardTitle>
              </CardHeader>
              <CardContent>
                {taskStats?.daily_trend ? (
                  <MiniBarChart data={taskStats.daily_trend} />
                ) : (
                  <p className="text-muted-foreground text-sm">暂无数据</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">设备任务排行</CardTitle>
              </CardHeader>
              <CardContent>
                {taskStats?.top_machines && taskStats.top_machines.length > 0 ? (
                  <div className="space-y-2">
                    {taskStats.top_machines.map((m) => (
                      <div key={m.name} className="flex items-center gap-2">
                        <span className="text-sm flex-1 truncate">{m.name}</span>
                        <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary/60 rounded-full"
                            style={{
                              width: `${(m.count / (taskStats.top_machines[0]?.count || 1)) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-sm text-muted-foreground w-8 text-right">
                          {m.count}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">暂无数据</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Issue Stats */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Issue 状态分布</CardTitle>
              </CardHeader>
              <CardContent>
                {issueStats?.status_distribution ? (
                  <DistributionList distribution={issueStats.status_distribution} />
                ) : (
                  <p className="text-muted-foreground text-sm">暂无数据</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Issue 优先级分布</CardTitle>
              </CardHeader>
              <CardContent>
                {issueStats?.priority_distribution ? (
                  <DistributionList distribution={issueStats.priority_distribution} />
                ) : (
                  <p className="text-muted-foreground text-sm">暂无数据</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Issue 创建趋势 (近 30 天)</CardTitle>
              </CardHeader>
              <CardContent>
                {issueStats?.daily_trend ? (
                  <MiniBarChart data={issueStats.daily_trend} />
                ) : (
                  <p className="text-muted-foreground text-sm">暂无数据</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">项目 Issue 排行</CardTitle>
              </CardHeader>
              <CardContent>
                {issueStats?.top_projects && issueStats.top_projects.length > 0 ? (
                  <div className="space-y-2">
                    {issueStats.top_projects.map((p) => (
                      <div key={p.name} className="flex items-center gap-2">
                        <span className="text-sm flex-1 truncate">{p.name}</span>
                        <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary/60 rounded-full"
                            style={{
                              width: `${(p.count / (issueStats.top_projects[0]?.count || 1)) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-sm text-muted-foreground w-8 text-right">
                          {p.count}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">暂无数据</p>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
