"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchIssues, createIssue, Issue, fetchMachines, fetchAgents, fetchLabels,
  Machine, Agent, Label as LabelType,
} from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton, SkeletonTable } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectGroup, SelectItem,
  SelectLabel, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PlusIcon, EyeIcon, ListIcon, LayoutGridIcon, ArrowUpDownIcon } from "lucide-react";
import { toast } from "sonner";

type StatusFilter = "all" | "todo" | "in_progress" | "done" | "cancelled";
type ViewMode = "list" | "kanban";
type SortKey = "updated" | "priority" | "created";

const STATUS_CHIPS: FilterChip<StatusFilter>[] = [
  { value: "all", label: "全部" },
  { value: "todo", label: "待办", dot: "bg-gray-400" },
  { value: "in_progress", label: "进行中", dot: "bg-blue-500" },
  { value: "done", label: "已完成", dot: "bg-green-500" },
  { value: "cancelled", label: "已取消", dot: "bg-red-400" },
];

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "updated", label: "最近更新" },
  { value: "created", label: "创建时间" },
  { value: "priority", label: "优先级" },
];

const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 };

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

// Kanban board inline component
function KanbanBoard({ issues }: { issues: Issue[] }) {
  const router = useRouter();
  const columns: { status: StatusFilter; label: string; color: string }[] = [
    { status: "todo", label: "待办", color: "border-t-gray-400" },
    { status: "in_progress", label: "进行中", color: "border-t-blue-500" },
    { status: "done", label: "已完成", color: "border-t-green-500" },
    { status: "cancelled", label: "已取消", color: "border-t-red-400" },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {columns.map((col) => {
        const colIssues = issues.filter((i) => i.status === col.status);
        return (
          <div key={col.status} className="space-y-3">
            <div className={`flex items-center gap-2 border-t-2 ${col.color} pt-2`}>
              <h3 className="text-sm font-medium">{col.label}</h3>
              <span className="text-xs text-muted-foreground bg-muted rounded-full px-1.5 py-0.5">
                {colIssues.length}
              </span>
            </div>
            <div className="space-y-2">
              {colIssues.map((issue) => {
                const pCfg = priorityConfig[issue.priority];
                return (
                  <Card
                    key={issue.id}
                    className="cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => router.push(`/issues/${issue.id}`)}
                  >
                    <CardContent className="p-3 space-y-2">
                      <p className="text-sm font-medium line-clamp-2">{issue.title}</p>
                      <div className="flex items-center justify-between">
                        <span className={`text-xs ${pCfg?.color}`}>{pCfg?.label}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {issue.issue_id}
                        </span>
                      </div>
                      {issue.labels && issue.labels.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {issue.labels.map((l) => (
                            <span
                              key={l.id}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-muted"
                              style={l.color ? { borderLeft: `3px solid ${l.color}` } : undefined}
                            >
                              {l.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function IssuesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [labelFilter, setLabelFilter] = useState<string>("");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["issues", statusFilter, labelFilter],
    queryFn: () =>
      fetchIssues({
        status: statusFilter === "all" ? undefined : statusFilter,
        label_id: labelFilter || undefined,
        limit: 200,
      }),
    refetchInterval: 10000,
  });

  const issues = (data?.issues ?? []).slice().sort((a, b) => {
    if (sortKey === "priority") return (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9);
    if (sortKey === "created") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });

  // Compute counts for filter chips
  const allIssues = data?.issues ?? [];
  const statusCounts: Record<string, number> = { all: allIssues.length };
  allIssues.forEach((i) => { statusCounts[i.status] = (statusCounts[i.status] || 0) + 1; });
  const chipsWithCounts = STATUS_CHIPS.map((c) => ({ ...c, count: statusCounts[c.value] ?? 0 }));

  const { data: machines } = useQuery({ queryKey: ["machines"], queryFn: fetchMachines });
  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchAgents({ is_enabled: true }),
  });
  const { data: labels } = useQuery({ queryKey: ["labels"], queryFn: fetchLabels });

  const mutation = useMutation({
    mutationFn: createIssue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      setOpen(false);
      toast.success("Issue 创建成功");
    },
    onError: (err: Error) => toast.error(`创建失败: ${err.message}`),
  });

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const title = fd.get("title") as string;
    const description = fd.get("description") as string;
    const priority = fd.get("priority") as string;
    const assigneeType = fd.get("assignee_type") as string;
    const assigneeId = fd.get("assignee_id") as string;
    if (!title.trim()) return;
    mutation.mutate({
      title, description, priority,
      assignee_type: assigneeType || undefined,
      assignee_id: assigneeId || undefined,
    });
    form.reset();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Issue 管理</h2>
          <p className="text-muted-foreground">跟踪工作项和执行历史</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <PlusIcon className="size-4 mr-1" />
          新建 Issue
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <FilterChips
          chips={chipsWithCounts}
          value={statusFilter}
          onChange={setStatusFilter}
        />
        <div className="flex items-center gap-2">
          <Select value={labelFilter} onValueChange={(v) => setLabelFilter(v ?? "")}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="标签" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">全部标签</SelectItem>
              {(labels ?? []).map((l: LabelType) => (
                <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
            <SelectTrigger className="w-32">
              <ArrowUpDownIcon className="size-3.5 mr-1" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex border rounded-md">
            <Button
              variant={viewMode === "list" ? "secondary" : "ghost"}
              size="icon-sm"
              onClick={() => setViewMode("list")}
              title="列表视图"
            >
              <ListIcon className="size-4" />
            </Button>
            <Button
              variant={viewMode === "kanban" ? "secondary" : "ghost"}
              size="icon-sm"
              onClick={() => setViewMode("kanban")}
              title="看板视图"
            >
              <LayoutGridIcon className="size-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <Card>
          <SkeletonTable rows={6} cols={6} />
        </Card>
      ) : issues.length === 0 ? (
        <Card>
          <div className="py-12 text-center text-muted-foreground">
            {statusFilter === "all"
              ? "暂无 Issue，点击右上角创建"
              : `暂无 ${STATUS_CHIPS.find((c) => c.value === statusFilter)?.label} Issue`}
          </div>
        </Card>
      ) : viewMode === "kanban" ? (
        <KanbanBoard issues={issues} />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>标题</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>优先级</TableHead>
                  <TableHead>任务数</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {issues.map((issue: Issue) => {
                  const pCfg = priorityConfig[issue.priority] ?? { label: issue.priority, color: "" };
                  return (
                    <TableRow
                      key={issue.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/issues/${issue.id}`)}
                    >
                      <TableCell>
                        <div className="space-y-0.5">
                          <p className="font-medium text-sm">{issue.title}</p>
                          <p className="font-mono text-xs text-muted-foreground">{issue.issue_id}</p>
                        </div>
                      </TableCell>
                      <TableCell><StatusBadge status={issue.status} /></TableCell>
                      <TableCell>
                        <span className={`text-sm font-medium ${pCfg.color}`}>{pCfg.label}</span>
                      </TableCell>
                      <TableCell className="text-sm">{issue.tasks?.length ?? 0}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTime(issue.updated_at)}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={(e) => { e.stopPropagation(); router.push(`/issues/${issue.id}`); }}
                          title="查看详情"
                        >
                          <EyeIcon className="size-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>新建 Issue</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="issue-title">标题</Label>
              <Input id="issue-title" name="title" placeholder="简要描述工作项..." required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="issue-desc">描述</Label>
              <Textarea id="issue-desc" name="description" placeholder="详细描述（可选）..." rows={4} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="issue-priority">优先级</Label>
              <Select name="priority" defaultValue="medium">
                <SelectTrigger id="issue-priority"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">低</SelectItem>
                  <SelectItem value="medium">中</SelectItem>
                  <SelectItem value="high">高</SelectItem>
                  <SelectItem value="urgent">紧急</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="issue-assignee-type">分配方式</Label>
              <Select name="assignee_type" defaultValue="">
                <SelectTrigger id="issue-assignee-type">
                  <SelectValue placeholder="不分配（放入任务池）" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">不分配</SelectItem>
                  <SelectItem value="machine">分配给设备</SelectItem>
                  <SelectItem value="agent">分配给智能体</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="issue-assignee">目标</Label>
              <Select name="assignee_id">
                <SelectTrigger id="issue-assignee">
                  <SelectValue placeholder="选择设备或智能体..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">—</SelectItem>
                  <SelectGroup>
                    <SelectLabel>设备</SelectLabel>
                    {(machines ?? []).map((m: Machine) => (
                      <SelectItem key={`machine-${m.id}`} value={m.id}>
                        {m.machine_name} ({m.agent_type})
                      </SelectItem>
                    ))}
                  </SelectGroup>
                  <SelectGroup>
                    <SelectLabel>智能体</SelectLabel>
                    {(agents ?? []).map((a: Agent) => (
                      <SelectItem key={`agent-${a.id}`} value={a.id}>{a.name}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>取消</Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "创建中..." : "创建"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
