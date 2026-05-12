"use client";

import React, { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchProject,
  fetchIssues,
  updateIssue,
  createIssue,
  fetchMachines,
  fetchAgents,
  fetchIssue,
  Issue,
  Machine,
  Agent,
  Project,
} from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PlusIcon, EyeIcon, EditIcon, ArrowLeftIcon, ListIcon, LayoutGridIcon } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { BoardView } from "@/components/kanban/board-view";

type ViewMode = "list" | "kanban";

type StatusFilter = "all" | "backlog" | "todo" | "in_progress" | "done" | "blocked" | "cancelled";

const STATUS_CHIPS: FilterChip<StatusFilter>[] = [
  { value: "all", label: "全部" },
  { value: "backlog", label: "待规划", dot: "bg-gray-300" },
  { value: "todo", label: "待办", dot: "bg-gray-400" },
  { value: "in_progress", label: "进行中", dot: "bg-blue-500" },
  { value: "done", label: "已完成", dot: "bg-green-500" },
  { value: "blocked", label: "被阻塞", dot: "bg-orange-500" },
  { value: "cancelled", label: "已取消", dot: "bg-red-400" },
];

const PRIORITY_OPTIONS = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "urgent", label: "紧急" },
];

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

export default function ProjectDetailPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("kanban");
  const [open, setOpen] = useState(false);
  const [selectedAssigneeType, setSelectedAssigneeType] = useState("");
  const [selectedAssigneeId, setSelectedAssigneeId] = useState("");
  const [selectedAgentCli, setSelectedAgentCli] = useState("");
  const [selectedPriority, setSelectedPriority] = useState("medium");

  const [editOpen, setEditOpen] = useState(false);
  const [editingIssue, setEditingIssue] = useState<Issue | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editSelectedAssigneeType, setEditSelectedAssigneeType] = useState("");
  const [editSelectedAssigneeId, setEditSelectedAssigneeId] = useState("");
  const [editSelectedAgentCli, setEditSelectedAgentCli] = useState("");
  const [editSelectedPriority, setEditSelectedPriority] = useState("medium");
  const [pendingEditIssue, setPendingEditIssue] = useState<Issue | null>(null);

  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => fetchProject(projectId),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["issues", "project", projectId, statusFilter],
    queryFn: () =>
      fetchIssues({
        project_id: projectId,
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: 200,
      }),
    refetchInterval: 10000,
  });

  const issues = (data?.issues ?? []).slice().sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  const statusCounts: Record<string, number> = { all: (data?.issues ?? []).length };
  (data?.issues ?? []).forEach((i) => {
    statusCounts[i.status] = (statusCounts[i.status] || 0) + 1;
  });
  const chipsWithCounts = STATUS_CHIPS.map((c) => ({
    ...c,
    count: statusCounts[c.value] ?? 0,
  }));

  const { data: machines } = useQuery({ queryKey: ["machines"], queryFn: fetchMachines });
  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchAgents({ is_enabled: true }),
  });

  const mutation = useMutation({
    mutationFn: createIssue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      setOpen(false);
      toast.success("Issue 创建成功");
    },
    onError: (err: Error) => toast.error(`创建失败: ${err.message}`),
  });

  const statusMutation = useMutation({
    mutationFn: (variables: { id: string; status: string }) =>
      updateIssue(variables.id, { status: variables.status }),
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ["issues"] });
      const queryKey = ["issues", "project", projectId, statusFilter];
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData<{ issues: Issue[]; total: number }>(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          issues: old.issues.map((i) => (i.id === id ? { ...i, status: status as Issue["status"] } : i)),
        };
      });
      return { previous, queryKey };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous && context?.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
      toast.error("状态更新失败");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });

  const priorityMutation = useMutation({
    mutationFn: ({ id, priority }: { id: string; priority: string }) =>
      updateIssue(id, { priority }),
    onMutate: async ({ id, priority }) => {
      await queryClient.cancelQueries({ queryKey: ["issues"] });
      const queryKey = ["issues", "project", projectId, statusFilter];
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData<{ issues: Issue[]; total: number }>(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          issues: old.issues.map((i) => (i.id === id ? { ...i, priority: priority as Issue["priority"] } : i)),
        };
      });
      return { previous, queryKey };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous && context?.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
      toast.error("优先级更新失败");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });

  const editMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateIssue>[1] }) =>
      updateIssue(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      setEditOpen(false);
      setEditingIssue(null);
      toast.success("Issue 已更新");
    },
    onError: (err: Error) => toast.error(`更新失败: ${err.message}`),
  });

  const openEditDialog = async (issue: Issue) => {
    try {
      const fullIssue = await fetchIssue(issue.id);
      setPendingEditIssue(fullIssue);
      setEditTitle(fullIssue.title);
      setEditDescription(fullIssue.description ?? "");
      setEditSelectedAssigneeType(fullIssue.assignee_type ?? "");
      setEditSelectedAssigneeId(fullIssue.assignee_id ?? "");
      setEditSelectedAgentCli(fullIssue.agent_cli_id ?? "");
      setEditSelectedPriority(fullIssue.priority ?? "medium");
    } catch {
      toast.error("获取Issue详情失败");
    }
  };

  React.useEffect(() => {
    if (pendingEditIssue) {
      setEditingIssue(pendingEditIssue);
      setEditOpen(true);
      setPendingEditIssue(null);
    }
  }, [pendingEditIssue]);

  React.useEffect(() => {
    if (editOpen && editingIssue) {
      setEditTitle(editingIssue.title);
      setEditDescription(editingIssue.description ?? "");
      setEditSelectedAssigneeType(editingIssue.assignee_type ?? "");
      setEditSelectedAssigneeId(editingIssue.assignee_id ?? "");
      setEditSelectedPriority(editingIssue.priority ?? "medium");
    }
  }, [editOpen, editingIssue]);

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const title = fd.get("title") as string;
    const description = fd.get("description") as string;
    const priority = fd.get("priority") as string;
    const assigneeType = fd.get("assignee_type") as string;
    const assigneeId = fd.get("assignee_id") as string;
    const agentCliId = fd.get("agent_cli_id") as string;
    if (!title.trim()) return;
    mutation.mutate({
      title,
      description,
      priority,
      project_id: projectId,
      assignee_type: assigneeType || undefined,
      assignee_id: assigneeId || undefined,
      agent_cli_id: agentCliId || undefined,
    });
    form.reset();
    setSelectedAssigneeType("");
    setSelectedAssigneeId("");
    setSelectedAgentCli("");
    setSelectedPriority("medium");
  };

  if (projectLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-muted rounded animate-pulse" />
        <div className="h-4 w-32 bg-muted rounded animate-pulse" />
        <SkeletonTable rows={6} cols={6} />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">项目不存在</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <Link href="/projects">
              <Button variant="ghost" size="icon-sm">
                <ArrowLeftIcon className="size-4" />
              </Button>
            </Link>
            <h2 className="text-2xl font-bold tracking-tight">{project.project_name}</h2>
          </div>
          <p className="text-muted-foreground text-sm font-mono ml-11">
            {project.project_id} · {project.root_path ?? "未设置路径"}
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <PlusIcon className="size-4 mr-1" />
          新建 Issue
        </Button>
      </div>

      {/* Project Info */}
      <Card>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4 py-4">
          <div>
            <p className="text-xs text-muted-foreground">最后活动时间</p>
            <p className="text-sm font-medium">{formatTime(project.last_activity_at)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">闲置时长</p>
            <p className="text-sm font-medium">
              {project.idle_hours !== null ? `${project.idle_hours}h` : "-"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">闲置阈值</p>
            <p className="text-sm font-medium">{project.idle_threshold_hours}h</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Issue 总数</p>
            <p className="text-sm font-medium">{statusCounts.all}</p>
          </div>
        </CardContent>
      </Card>

      {/* Filter bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <FilterChips
          chips={chipsWithCounts}
          value={statusFilter}
          onChange={setStatusFilter}
        />
        <div className="flex border rounded-md">
          <Button
            variant={viewMode === "kanban" ? "secondary" : "ghost"}
            size="icon-sm"
            onClick={() => setViewMode("kanban")}
            title="看板视图"
          >
            <LayoutGridIcon className="size-4" />
          </Button>
          <Button
            variant={viewMode === "list" ? "secondary" : "ghost"}
            size="icon-sm"
            onClick={() => setViewMode("list")}
            title="列表视图"
          >
            <ListIcon className="size-4" />
          </Button>
        </div>
      </div>

      {/* Issues content */}
      {isLoading ? (
        <Card><SkeletonTable rows={6} cols={6} /></Card>
      ) : issues.length === 0 ? (
        <Card>
          <div className="py-12 text-center text-muted-foreground">
            暂无 Issue
          </div>
        </Card>
      ) : viewMode === "kanban" ? (
        <BoardView
          issues={issues}
          onStatusChange={(id, status) => statusMutation.mutate({ id, status })}
          onPriorityChange={(id, priority) => priorityMutation.mutate({ id, priority })}
          onEdit={openEditDialog}
        />
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
                {issues.map((issue: Issue) => (
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
                      <span className="text-sm font-medium">
                        {PRIORITY_OPTIONS.find((o) => o.value === issue.priority)?.label ?? issue.priority}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">{issue.tasks?.length ?? 0}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTime(issue.updated_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={(e) => { e.stopPropagation(); openEditDialog(issue); }}
                          title="修改"
                        >
                          <EditIcon className="size-3.5" />
                        </Button>
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={(e) => { e.stopPropagation(); router.push(`/issues/${issue.id}`); }}
                          title="查看详情"
                        >
                          <EyeIcon className="size-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
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
              <Select name="priority" value={selectedPriority} onValueChange={(v) => setSelectedPriority(v ?? "medium")}>
                <SelectTrigger id="issue-priority">
                  <SelectValue>{PRIORITY_OPTIONS.find((o) => o.value === selectedPriority)?.label}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="issue-assignee-type">分配方式</Label>
              <Select name="assignee_type" value={selectedAssigneeType} onValueChange={(v) => { setSelectedAssigneeType(v || ""); setSelectedAssigneeId(""); }}>
                <SelectTrigger id="issue-assignee-type">
                  <SelectValue placeholder="不分配（放入任务池）" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">不分配（放入任务池）</SelectItem>
                  <SelectItem value="machine">分配给设备</SelectItem>
                  <SelectItem value="agent">分配给智能体</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {selectedAssigneeType === "machine" && (
              <div className="space-y-2">
                <Label htmlFor="issue-machine">选择设备</Label>
                <Select name="assignee_id" value={selectedAssigneeId} onValueChange={(v) => { setSelectedAssigneeId(v ?? ""); setSelectedAgentCli(""); }}>
                  <SelectTrigger id="issue-machine">
                    <SelectValue>{(machines ?? []).find(m => m.id === selectedAssigneeId)?.machine_name || "选择设备..."}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {(machines ?? []).map((m: Machine) => (
                      <SelectItem key={m.id} value={m.id}>
                        {m.machine_name} ({(m.available_agents ?? []).map(a => a.agent_type).join(", ") || m.agent_type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {selectedAssigneeType === "agent" && (
              <div className="space-y-2">
                <Label htmlFor="issue-agent">选择智能体</Label>
                <Select name="assignee_id" value={selectedAssigneeId} onValueChange={(v) => setSelectedAssigneeId(v ?? "")}>
                  <SelectTrigger id="issue-agent">
                    <SelectValue>{(agents ?? []).find(a => a.id === selectedAssigneeId)?.name || "选择智能体..."}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {(agents ?? []).map((a: Agent) => (
                      <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {(() => {
              const selectedMachine = (machines ?? []).find(m => m.id === selectedAssigneeId);
              const availableAgents = selectedMachine?.available_agents;
              if (selectedAssigneeType !== "machine" || !selectedAssigneeId || !availableAgents || availableAgents.length <= 1) return null;
              const selectedAgent = availableAgents.find((a) => (a.cli_id || a.agent_type) === selectedAgentCli);
              return (
                <div className="space-y-2">
                  <Label htmlFor="issue-agent-cli">Agent CLI</Label>
                  <Select name="agent_cli_id" value={selectedAgentCli} onValueChange={(v) => setSelectedAgentCli(v ?? "")}>
                    <SelectTrigger id="issue-agent-cli">
                      <SelectValue>{selectedAgent ? `${selectedAgent.agent_type} v${selectedAgent.version}` : "默认（第一个可用）"}</SelectValue>
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
              );
            })()}
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>取消</Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "创建中..." : "创建"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>编辑 Issue</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!editingIssue) return;
              editMutation.mutate({
                id: editingIssue.id,
                data: {
                  title: editTitle,
                  description: editDescription,
                  priority: editSelectedPriority,
                  assignee_type: editSelectedAssigneeType || undefined,
                  assignee_id: editSelectedAssigneeId || undefined,
                  agent_cli_id: editSelectedAgentCli || undefined,
                },
              });
            }}
            className="space-y-4"
          >
            <div className="space-y-2">
              <Label htmlFor="edit-title">标题</Label>
              <Input
                id="edit-title"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-desc">描述</Label>
              <Textarea
                id="edit-desc"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                rows={4}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-priority">优先级</Label>
              <Select value={editSelectedPriority} onValueChange={(v) => setEditSelectedPriority(v ?? "medium")}>
                <SelectTrigger id="edit-priority">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-assignee-type">分配方式</Label>
              <Select value={editSelectedAssigneeType} onValueChange={(v) => { setEditSelectedAssigneeType(v || ""); setEditSelectedAssigneeId(""); setEditSelectedAgentCli(""); }}>
                <SelectTrigger id="edit-assignee-type">
                  <SelectValue>{editSelectedAssigneeType === "machine" ? "分配给设备" : editSelectedAssigneeType === "agent" ? "分配给智能体" : "不分配"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">不分配（放入任务池）</SelectItem>
                  <SelectItem value="machine">分配给设备</SelectItem>
                  <SelectItem value="agent">分配给智能体</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {editSelectedAssigneeType === "machine" && (
              <div className="space-y-2">
                <Label htmlFor="edit-machine">选择设备</Label>
                <Select value={editSelectedAssigneeId} onValueChange={(v) => { setEditSelectedAssigneeId(v ?? ""); setEditSelectedAgentCli(""); }}>
                  <SelectTrigger id="edit-machine">
                    <SelectValue>{(machines ?? []).find(m => m.id === editSelectedAssigneeId)?.machine_name || "选择设备..."}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {(machines ?? []).map((m: Machine) => (
                      <SelectItem key={m.id} value={m.id}>
                        {m.machine_name} ({(m.available_agents ?? []).map(a => a.agent_type).join(", ") || m.agent_type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {editSelectedAssigneeType === "agent" && (
              <div className="space-y-2">
                <Label htmlFor="edit-agent">选择智能体</Label>
                <Select value={editSelectedAssigneeId} onValueChange={(v) => setEditSelectedAssigneeId(v ?? "")}>
                  <SelectTrigger id="edit-agent">
                    <SelectValue>{(agents ?? []).find(a => a.id === editSelectedAssigneeId)?.name || "选择智能体..."}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {(agents ?? []).map((a: Agent) => (
                      <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {editSelectedAssigneeType === "machine" && editSelectedAssigneeId && (() => {
              const selectedMachine = (machines ?? []).find(m => m.id === editSelectedAssigneeId);
              const availableAgents = selectedMachine?.available_agents;
              if (!availableAgents || availableAgents.length <= 1) return null;
              return (
                <div className="space-y-2">
                  <Label htmlFor="edit-agent-cli">Agent CLI</Label>
                  <Select value={editSelectedAgentCli} onValueChange={(v) => setEditSelectedAgentCli(v ?? "")}>
                    <SelectTrigger id="edit-agent-cli">
                      <SelectValue>{availableAgents.find(a => (a.cli_id || a.agent_type) === editSelectedAgentCli) ? `${availableAgents.find(a => (a.cli_id || a.agent_type) === editSelectedAgentCli)?.agent_type} v${availableAgents.find(a => (a.cli_id || a.agent_type) === editSelectedAgentCli)?.version}` : "默认（第一个可用）"}</SelectValue>
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
              );
            })()}
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>取消</Button>
              <Button type="submit" disabled={editMutation.isPending}>
                {editMutation.isPending ? "保存中..." : "保存"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
