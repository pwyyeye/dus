"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  fetchAgents,
  fetchMachines,
  fetchSkills,
  createAgent,
  updateAgent,
  deleteAgent,
  Skill,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PlusIcon, PencilIcon, TrashIcon, EyeIcon } from "lucide-react";
import { toast } from "sonner";
import { SkeletonTable } from "@/components/ui/skeleton";

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

export default function AgentsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  const { data: agents, isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchAgents(),
    refetchInterval: 15000,
  });

  const { data: machines } = useQuery({
    queryKey: ["machines"],
    queryFn: fetchMachines,
  });

  const { data: skills } = useQuery({
    queryKey: ["skills"],
    queryFn: () => fetchSkills(),
  });

  const createMutation = useMutation({
    mutationFn: createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      setOpen(false);
      toast.success("智能体创建成功");
    },
    onError: (err: Error) => toast.error(`创建失败: ${err.message}`),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateAgent>[1] }) =>
      updateAgent(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      setEditing(null);
      toast.success("智能体更新成功");
    },
    onError: (err: Error) => toast.error(`更新失败: ${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      toast.success("智能体已删除");
    },
    onError: (err: Error) => toast.error(`删除失败: ${err.message}`),
  });

  const editingAgent = editing ? agents?.find((a) => a.id === editing) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">智能体管理</h2>
          <p className="text-muted-foreground">管理绑定到设备的智能体配置</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <PlusIcon className="size-4 mr-1" />
          新建智能体
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>智能体列表</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <SkeletonTable rows={5} cols={8} />
          ) : !agents?.length ? (
            <div className="py-8 text-center text-muted-foreground">暂无智能体，点击右上角创建</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>绑定设备</TableHead>
                  <TableHead>绑定 CLI</TableHead>
                  <TableHead>模型</TableHead>
                  <TableHead>技能</TableHead>
                  <TableHead>并发上限</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {agents.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <div className="space-y-0.5">
                        <p className="font-medium text-sm">{a.name}</p>
                        {a.description && (
                          <p className="text-xs text-muted-foreground line-clamp-1">{a.description}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {a.machine?.machine_name ?? a.machine_id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {a.bound_cli_type ? (
                        <Badge variant="outline">{a.bound_cli_type}</Badge>
                      ) : (
                        <span className="text-muted-foreground">默认</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {a.model || "默认"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {a.skills?.length ? (
                          a.skills.map((s) => (
                            <Badge key={s.id} variant="outline" className="text-xs">
                              {categoryIcons[s.category ?? "other"] ?? "📦"} {s.name}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{a.max_concurrent_tasks}</TableCell>
                    <TableCell>
                      <Badge variant={a.is_enabled ? "default" : "secondary"}>
                        {a.is_enabled ? "启用" : "禁用"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={() => router.push(`/agents/${a.id}`)}
                          title="查看详情"
                        >
                          <EyeIcon className="size-3.5" />
                        </Button>
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={() => setEditing(a.id)}
                          title="编辑"
                        >
                          <PencilIcon className="size-3.5" />
                        </Button>
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={() => {
                            if (confirm("确认删除此智能体？")) deleteMutation.mutate(a.id);
                          }}
                          title="删除"
                        >
                          <TrashIcon className="size-3.5 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <AgentFormDialog
        open={open}
        onOpenChange={setOpen}
        machines={machines ?? []}
        skills={skills ?? []}
        isPending={createMutation.isPending}
        title="新建智能体"
        onSave={(data) => createMutation.mutate(data as Parameters<typeof createAgent>[0])}
      />

      {/* Edit Dialog */}
      <AgentFormDialog
        open={!!editing}
        onOpenChange={(v) => { if (!v) setEditing(null); }}
        machines={machines ?? []}
        skills={skills ?? []}
        isPending={updateMutation.isPending}
        title="编辑智能体"
        initial={editingAgent}
        onSave={(data) => {
          if (editing) updateMutation.mutate({ id: editing, data: data as Parameters<typeof updateAgent>[1] });
        }}
      />
    </div>
  );
}

function AgentFormDialog({
  open,
  onOpenChange,
  machines,
  skills,
  isPending,
  onSave,
  title,
  initial,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  machines: { id: string; machine_id: string; machine_name: string; agent_type: string; available_agents?: Array<{ cli_id: string; agent_type: string; path: string; version: string }> }[];
  skills: Skill[];
  isPending: boolean;
  onSave: (data: Record<string, unknown>) => void;
  title: string;
  initial?: {
    id?: string;
    name?: string;
    description?: string | null;
    machine_id?: string;
    instructions?: string | null;
    model?: string | null;
    max_concurrent_tasks?: number;
    bound_cli_id?: string | null;
    bound_cli_type?: string | null;
    skills?: Skill[];
  } | null;
}) {
  const [selectedSkills, setSelectedSkills] = useState<string[]>(
    initial?.skills?.map((s) => s.id) ?? []
  );
  const [selectedMachineId, setSelectedMachineId] = useState<string | null>(
    initial?.machine_id ?? null
  );
  const [selectedCliId, setSelectedCliId] = useState<string | null>(
    initial?.bound_cli_id ?? null
  );

  const selectedMachine = machines.find((m) => m.id === (selectedMachineId || initial?.machine_id));
  const availableClis = selectedMachine?.available_agents ?? [];

  const toggleSkill = (skillId: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skillId)
        ? prev.filter((id) => id !== skillId)
        : [...prev, skillId]
    );
  };

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const name = fd.get("name") as string;
    const machine_id = fd.get("machine_id") as string;
    if (!name.trim() || !machine_id) return;

    const data: Record<string, unknown> = {
      name: name.trim(),
      machine_id,
      skill_ids: selectedSkills,
    };
    const description = fd.get("description") as string;
    const instructions = fd.get("instructions") as string;
    const model = fd.get("model") as string;
    const maxConcurrent = fd.get("max_concurrent_tasks") as string;
    const bound_cli_id = selectedCliId || undefined;

    if (description) data.description = description;
    if (instructions) data.instructions = instructions;
    if (model) data.model = model;
    if (maxConcurrent) data.max_concurrent_tasks = parseInt(maxConcurrent, 10);
    if (bound_cli_id) data.bound_cli_id = bound_cli_id;

    onSave(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="agent-name">名称 *</Label>
            <Input id="agent-name" name="name" defaultValue={initial?.name ?? ""} placeholder="例: 安全审计专家" required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-desc">描述</Label>
            <Textarea id="agent-desc" name="description" defaultValue={initial?.description ?? ""} placeholder="智能体用途说明..." rows={2} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-machine">绑定设备 *</Label>
            <Select
              name="machine_id"
              defaultValue={initial?.machine_id}
              onValueChange={(val) => {
                setSelectedMachineId(val);
                setSelectedCliId(null);
              }}
            >
              <SelectTrigger id="agent-machine">
                <SelectValue placeholder="选择设备..." />
              </SelectTrigger>
              <SelectContent>
                {machines.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.machine_name} ({m.available_agents?.map(a => a.agent_type).join(", ") ?? m.agent_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {availableClis.length > 1 && (
            <div className="space-y-2">
              <Label htmlFor="agent-cli">绑定 CLI</Label>
              <Select
                name="bound_cli_id"
                value={selectedCliId ?? ""}
                onValueChange={setSelectedCliId}
              >
                <SelectTrigger id="agent-cli">
                  <SelectValue placeholder="使用默认 CLI（第一个）..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">使用默认 CLI（第一个）</SelectItem>
                  {availableClis.map((cli) => (
                    <SelectItem key={cli.cli_id} value={cli.cli_id}>
                      {cli.agent_type} (v{cli.version})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                指定此智能体使用哪个 CLI 执行任务
              </p>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="agent-instructions">系统指令</Label>
            <Textarea id="agent-instructions" name="instructions" defaultValue={initial?.instructions ?? ""} placeholder="注入到 AI 的系统提示词..." rows={3} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="agent-model">模型</Label>
              <Input id="agent-model" name="model" defaultValue={initial?.model ?? ""} placeholder="例: claude-sonnet-4-6" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-max-concurrent">并发上限</Label>
              <Input id="agent-max-concurrent" name="max_concurrent_tasks" type="number" min={1} max={20} defaultValue={initial?.max_concurrent_tasks ?? 3} />
            </div>
          </div>
          {skills.length > 0 && (
            <div className="space-y-2">
              <Label>技能</Label>
              <div className="border rounded-md p-3 space-y-2 max-h-40 overflow-y-auto">
                {skills.map((skill) => (
                  <div key={skill.id} className="flex items-center gap-2">
                    <Checkbox
                      id={`skill-${skill.id}`}
                      checked={selectedSkills.includes(skill.id)}
                      onCheckedChange={() => toggleSkill(skill.id)}
                    />
                    <Label htmlFor={`skill-${skill.id}`} className="text-sm font-normal cursor-pointer">
                      {categoryIcons[skill.category ?? "other"] ?? "📦"} {skill.name}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "保存中..." : "保存"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
