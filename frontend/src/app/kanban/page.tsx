"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchIssues, Issue } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EyeIcon } from "lucide-react";

const columns = [
  { status: "todo", label: "待办", color: "bg-gray-100" },
  { status: "in_progress", label: "进行中", color: "bg-blue-50" },
  { status: "done", label: "已完成", color: "bg-green-50" },
  { status: "cancelled", label: "已取消", color: "bg-red-50" },
] as const;

const priorityConfig: Record<string, { label: string; color: string }> = {
  low: { label: "低", color: "text-muted-foreground" },
  medium: { label: "中", color: "text-blue-600" },
  high: { label: "高", color: "text-orange-600" },
  urgent: { label: "紧急", color: "text-red-600" },
};

function IssueCard({ issue }: { issue: Issue }) {
  const router = useRouter();
  const pConfig = priorityConfig[issue.priority] ?? { label: issue.priority, color: "" };

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => router.push(`/issues/${issue.id}`)}
    >
      <CardContent className="p-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium line-clamp-2">{issue.title}</p>
          <span className={`text-xs font-medium shrink-0 ${pConfig.color}`}>
            {pConfig.label}
          </span>
        </div>
        <p className="text-xs text-muted-foreground font-mono">{issue.issue_id}</p>
        {issue.labels && issue.labels.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {issue.labels.slice(0, 3).map((label) => (
              <Badge
                key={label.id}
                variant="outline"
                className="text-xs py-0"
                style={label.color ? { borderColor: label.color, color: label.color } : undefined}
              >
                {label.name}
              </Badge>
            ))}
            {issue.labels.length > 3 && (
              <span className="text-xs text-muted-foreground">+{issue.labels.length - 3}</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function KanbanPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["issues"],
    queryFn: () => fetchIssues({ limit: 200 }),
    refetchInterval: 15000,
  });

  const issues = data?.issues ?? [];

  const grouped = columns.reduce(
    (acc, col) => {
      acc[col.status] = issues.filter((i) => i.status === col.status);
      return acc;
    },
    {} as Record<string, Issue[]>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">看板视图</h2>
        <p className="text-muted-foreground">按状态查看 Issue 分布</p>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {columns.map((col) => (
            <div key={col.status} className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm">{col.label}</h3>
                <Badge variant="secondary">{grouped[col.status].length}</Badge>
              </div>
              <div className={`rounded-lg p-2 min-h-[400px] space-y-2 ${col.color}`}>
                {grouped[col.status].length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-4">无</p>
                ) : (
                  grouped[col.status].map((issue) => (
                    <IssueCard key={issue.id} issue={issue} />
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
