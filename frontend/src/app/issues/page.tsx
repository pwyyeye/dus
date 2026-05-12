"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchIssues, createIssue, updateIssue, Issue, fetchMachines, fetchAgents, fetchLabels, fetchProjects, fetchIssue,
  Machine, Agent, Label as LabelType, Project,
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
import { PlusIcon, EyeIcon, EditIcon, ListIcon, LayoutGridIcon, ArrowUpDownIcon } from "lucide-react";
import { toast } from "sonner";
import { BoardView } from "@/components/kanban/board-view";

type StatusFilter = "all" | "backlog" | "todo" | "in_progress" | "done" | "blocked" | "cancelled";
type ViewMode = "list" | "kanban";
type SortKey = "updated" | "priority" | "created";

const STATUS_CHIPS: FilterChip<StatusFilter>[] = [
  { value: "all", label: "全部" },
  { value: "backlog", label: "待办", dot: "bg-gray-300" },
  { value: "todo", label: "计划中", dot: "bg-gray-400" },
  { value: "in_progress", label: "进行中", dot: "bg-blue-500" },
  { value: "done", label: "已完成", dot: "bg-green-500" },
  { value: "blocked", label: "被阻塞", dot: "bg-orange-500" },
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

const PRIORITY_OPTIONS = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "urgent", label: "紧急" },
];

const ASSIGNEE_TYPE_OPTIONS = [
  { value: "", label: "不分配" },
  { value: "machine", label: "分配给设备" },
  { value: "agent", label: "分配给智能体" },
];

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}


export default function IssuesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [labelFilter, setLabelFilter] = useState<string>("");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [open, setOpen] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [selectedProjectName, setSelectedProjectName] = useState<string>("");
  const [selectedAssigneeType, setSelectedAssigneeType] = useState("");
  const [selectedAssigneeId, setSelectedAssigneeId] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [editingIssue, setEditingIssue] = useState<Issue | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editSelectedProjectName, setEditSelectedProjectName] = useState("");
  const [editSelectedAssigneeType, setEditSelectedAssigneeType] = useState("");
  const [editSelectedAssigneeId, setEditSelectedAssigneeId] = useState("");
  const [editSelectedAgentCli, setEditSelectedAgentCli] = useState("");
  const [editSelectedPriority, setEditSelectedPriority] = useState("medium");
  const [pendingEditIssue, setPendingEditIssue] = useState<Issue | null>(null);
  const [selectedPriority, setSelectedPriority] = useState("medium");
  const [selectedAgentCli, setSelectedAgentCli] = useState("");

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
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });

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
    mutationFn: (variables: { id: string; status: string }) => {
      console.log("[DEBUG statusMutation] Calling updateIssue:", variables.id, variables.status);
      return updateIssue(variables.id, { status: variables.status });
    },
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ["issues"] });
      const queryKey = ["issues", statusFilter, labelFilter];
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
    onError: (err, vars, context) => {
      console.error("[DEBUG statusMutation] Error:", err, "vars:", vars);
      if (context?.previous && context?.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
      toast.error("状态更新失败: " + (err?.message || String(err)));
    },
    onSuccess: (data, vars) => {
      console.log("[DEBUG statusMutation] Success! data:", data, "vars:", vars);
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
      const queryKey = ["issues", statusFilter, labelFilter];
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
      const proj = (projects ?? []).find((p: Project) => p.id === fullIssue.project_id);
      setEditSelectedProjectName(proj?.project_name ?? "");
    } catch (err) {
      toast.error("获取Issue详情失败");
    }
  };

  // Open dialog after state is set
  React.useEffect(() => {
    if (pendingEditIssue) {
      setEditingIssue(pendingEditIssue);
      setEditOpen(true);
      setPendingEditIssue(null);
    }
  }, [pendingEditIssue]);

  // Sync form state when dialog opens
  React.useEffect(() => {
    if (editOpen && editingIssue) {
      setEditTitle(editingIssue.title);
      setEditDescription(editingIssue.description ?? "");
      setEditSelectedAssigneeType(editingIssue.assignee_type ?? "");
      setEditSelectedAssigneeId(editingIssue.assignee_id ?? "");
      setEditSelectedPriority(editingIssue.priority ?? "medium");
      const proj = (projects ?? []).find((p: Project) => p.id === editingIssue.project_id);
      setEditSelectedProjectName(proj?.project_name ?? "");
    }
  }, [editOpen, editingIssue, projects]);

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
      title, description, priority,
      project_id: selectedProjectId || undefined,
      assignee_type: assigneeType || undefined,
      assignee_id: assigneeId || undefined,
      agent_cli_id: agentCliId || undefined,
    });
    form.reset();
    setSelectedProjectId("");
    setSelectedProjectName("");
    setSelectedAssigneeType("");
    setSelectedAssigneeId("");
    setSelectedPriority("medium");
    setSelectedAgentCli("");
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
        <BoardView
          issues={issues}
          onStatusChange={(id, status) => statusMutation.mutate({ id, status })}
          onPriorityChange={(id, priority) => priorityMutation.mutate({ id, priority })}
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
              <Label htmlFor="issue-project">绑定项目</Label>
              <Select value={selectedProjectName} onValueChange={(v) => {
                  const p = (projects ?? []).find((x: Project) => x.project_name === v);
                  setSelectedProjectId(p?.id ?? "");
                  setSelectedProjectName(v || "");
                }}>
                <SelectTrigger id="issue-project">
                  <SelectValue placeholder="不绑定（无路径约束）" />
                </SelectTrigger>
                <SelectContent>
                  {(projects ?? []).filter((p: Project) => p.root_path).map((p: Project) => (
                    <SelectItem key={p.id} value={p.project_name}>
                      {p.project_name} <span className="text-muted-foreground text-xs ml-1">{p.root_path}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedProjectId && (
                <p className="text-xs text-muted-foreground">
                  绑定后 Agent CLI 将在项目路径下操作
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="issue-priority">优先级</Label>
              <Select name="priority" value={selectedPriority} onValueChange={(v) => setSelectedPriority(v ?? "medium")}>
                <SelectTrigger id="issue-priority">
                  <SelectValue>{PRIORITY_OPTIONS.find(o => o.value === selectedPriority)?.label}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="issue-assignee-type">分配方式</Label>
              <Select name="assignee_type" value={selectedAssigneeType} onValueChange={(v) => { setSelectedAssigneeType(v || ""); setSelectedAssigneeId(""); }}>
                <SelectTrigger id="issue-assignee-type">
                  <SelectValue>{ASSIGNEE_TYPE_OPTIONS.find(o => o.value === selectedAssigneeType)?.label || "不分配（放入任务池）"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {ASSIGNEE_TYPE_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedAssigneeType === "machine" && (
              <div className="space-y-2">
                <Label htmlFor="issue-assignee">目标设备</Label>
                <Select name="assignee_id" value={selectedAssigneeId} onValueChange={(v) => setSelectedAssigneeId(v || "")}>
                  <SelectTrigger id="issue-assignee">
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
                <Label htmlFor="issue-assignee">目标智能体</Label>
                <Select name="assignee_id" value={selectedAssigneeId} onValueChange={(v) => setSelectedAssigneeId(v || "")}>
                  <SelectTrigger id="issue-assignee">
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
              const selectedAgent = availableAgents.find((a: { cli_id?: string; agent_type: string; version: string }) => (a.cli_id || a.agent_type) === selectedAgentCli);
              return (
                <div className="space-y-2">
                  <Label htmlFor="issue-agent-cli">Agent CLI</Label>
                  <Select name="agent_cli_id" value={selectedAgentCli} onValueChange={(v) => setSelectedAgentCli(v ?? "")}>
                    <SelectTrigger id="issue-agent-cli">
                      <SelectValue>{selectedAgent ? `${selectedAgent.agent_type} v${selectedAgent.version}` : "默认（第一个可用）"}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {availableAgents.map((a: { cli_id?: string; agent_type: string; version: string }) => (
                        <SelectItem key={a.cli_id || a.agent_type} value={a.cli_id || a.agent_type}>
                          {a.agent_type} <span className="text-muted-foreground text-xs ml-1">v{a.version}</span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              );
            })()}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>取消</Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "创建中..." : "创建"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editOpen} onOpenChange={(open) => { if (!open) { setEditOpen(false); setEditingIssue(null); setEditSelectedAgentCli(""); } }}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>修改 Issue</DialogTitle>
          </DialogHeader>
          <form key={`edit-form-${editingIssue?.id}`} onSubmit={(e) => {
            e.preventDefault();
            if (!editingIssue) return;
            const formData = new FormData(e.currentTarget);
            const proj = (projects ?? []).find((p: Project) => p.project_name === editSelectedProjectName);
            editMutation.mutate({
              id: editingIssue.id,
              data: {
                title: editTitle,
                description: editDescription || undefined,
                priority: formData.get("priority") as string,
                project_id: proj?.id ?? undefined,
                assignee_type: editSelectedAssigneeType || undefined,
                assignee_id: editSelectedAssigneeId || undefined,
                agent_cli_id: formData.get("agent_cli_id") as string || undefined,
              },
            });
          }} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-title">标题</Label>
              <Input id="edit-title" name="title" defaultValue={editTitle} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-desc">描述</Label>
              <textarea
                id="edit-desc"
                name="description"
                className="flex min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-base transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50"
                defaultValue={editDescription}
                rows={4}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-project">绑定项目</Label>
              <Select value={editSelectedProjectName} onValueChange={(v) => {
                  setEditSelectedProjectName(v || "");
                }}>
                <SelectTrigger id="edit-project">
                  <SelectValue placeholder="不绑定（无路径约束）" />
                </SelectTrigger>
                <SelectContent>
                  {(projects ?? []).filter((p: Project) => p.root_path).map((p: Project) => (
                    <SelectItem key={p.id} value={p.project_name}>
                      {p.project_name} <span className="text-muted-foreground text-xs ml-1">{p.root_path}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-priority">优先级</Label>
              <Select name="priority" value={editSelectedPriority} onValueChange={(v) => setEditSelectedPriority(v ?? "medium")}>
                <SelectTrigger id="edit-priority">
                  <SelectValue>{PRIORITY_OPTIONS.find(o => o.value === editSelectedPriority)?.label}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-assignee-type">分配方式</Label>
              <Select name="assignee_type" value={editSelectedAssigneeType} onValueChange={(v) => { setEditSelectedAssigneeType(v || ""); setEditSelectedAssigneeId(""); }}>
                <SelectTrigger id="edit-assignee-type">
                  <SelectValue>{ASSIGNEE_TYPE_OPTIONS.find(o => o.value === editSelectedAssigneeType)?.label || "不分配（放入任务池）"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">不分配</SelectItem>
                  <SelectItem value="machine">分配给设备</SelectItem>
                  <SelectItem value="agent">分配给智能体</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {editSelectedAssigneeType === "machine" && (
              <div className="space-y-2">
                <Label htmlFor="edit-assignee">目标设备</Label>
                <Select name="assignee_id" value={editSelectedAssigneeId} onValueChange={(v) => setEditSelectedAssigneeId(v || "")}>
                  <SelectTrigger id="edit-assignee">
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
            {(() => {
              const selectedMachine = (machines ?? []).find(m => m.id === editSelectedAssigneeId);
              const availableAgents = selectedMachine?.available_agents;
              if (editSelectedAssigneeType !== "machine" || !editSelectedAssigneeId || !availableAgents || availableAgents.length <= 1) return null;
              const selectedAgent = availableAgents.find((a: { cli_id?: string; agent_type: string; version: string }) => (a.cli_id || a.agent_type) === editSelectedAgentCli);
              return (
                <div className="space-y-2">
                  <Label htmlFor="edit-agent-cli">Agent CLI</Label>
                  <Select name="agent_cli_id" value={editSelectedAgentCli} onValueChange={(v) => setEditSelectedAgentCli(v ?? "")}>
                    <SelectTrigger id="edit-agent-cli">
                      <SelectValue>{selectedAgent ? `${selectedAgent.agent_type} v${selectedAgent.version}` : "默认（第一个可用）"}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {availableAgents.map((a: { cli_id?: string; agent_type: string; version: string }) => (
                        <SelectItem key={a.cli_id || a.agent_type} value={a.cli_id || a.agent_type}>
                          {a.agent_type} <span className="text-muted-foreground text-xs ml-1">v{a.version}</span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              );
            })()}
            {editSelectedAssigneeType === "agent" && (
              <div className="space-y-2">
                <Label htmlFor="edit-assignee">目标智能体</Label>
                <Select name="assignee_id" value={editSelectedAssigneeId} onValueChange={(v) => setEditSelectedAssigneeId(v || "")}>
                  <SelectTrigger id="edit-assignee">
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
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => { setEditOpen(false); setEditingIssue(null); setEditSelectedAgentCli(""); }}>取消</Button>
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
