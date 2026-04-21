"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchProjects, createProject } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

function formatTime(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function formatIdleHours(hours: number | null): string {
  if (hours === null) return "-";
  if (hours < 1) return "<1h";
  return `${Math.floor(hours)}h`;
}

type IdleStatus = "normal" | "warning" | "overdue";

function getIdleStatus(idleHours: number | null, thresholdHours: number): IdleStatus {
  if (idleHours === null) return "normal";
  if (idleHours >= thresholdHours * 2) return "overdue";
  if (idleHours >= thresholdHours) return "warning";
  return "normal";
}

const idleStatusConfig: Record<IdleStatus, { label: string; variant: "default" | "secondary" | "destructive"; className: string }> = {
  normal: { label: "正常", variant: "default", className: "bg-green-500" },
  warning: { label: "预警", variant: "secondary", className: "bg-yellow-500" },
  overdue: { label: "逾期", variant: "destructive", className: "bg-red-500" },
};

interface ProjectCardProps {
  project: {
    id: string;
    project_id: string;
    project_name: string;
    root_path: string | null;
    idle_threshold_hours: number;
    last_activity_at: string | null;
    idle_hours: number | null;
    created_at: string;
  };
}

function ProjectCard({ project }: ProjectCardProps) {
  const idleStatus = getIdleStatus(project.idle_hours, project.idle_threshold_hours);
  const statusConfig = idleStatusConfig[idleStatus];

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base">{project.project_name}</CardTitle>
            <CardDescription className="font-mono text-xs">
              {project.project_id}
            </CardDescription>
          </div>
          <Badge
            variant={statusConfig.variant}
            className={cn("shrink-0", statusConfig.className.includes("bg-") && "text-white")}
          >
            {statusConfig.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">项目路径</span>
            <span className="font-mono text-xs truncate max-w-[200px]" title={project.root_path ?? "-"}>
              {project.root_path ?? "-"}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">最后活动时间</span>
            <span className="text-xs">
              {formatTime(project.last_activity_at)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">闲置时长</span>
            <span className={cn(
              "font-medium",
              idleStatus === "overdue" && "text-red-600",
              idleStatus === "warning" && "text-yellow-600"
            )}>
              {formatIdleHours(project.idle_hours)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">闲置阈值</span>
            <span className="text-xs">{project.idle_threshold_hours}h</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ProjectsPage() {
  const [open, setOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [rootPath, setRootPath] = useState("");
  const queryClient = useQueryClient();

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
    refetchInterval: 30000,
  });

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
      setProjectName("");
      setRootPath("");
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) return;
    mutation.mutate({
      project_name: projectName,
      root_path: rootPath || undefined,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">项目状态</h2>
          <p className="text-muted-foreground">查看所有项目及其闲置状态</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button />}>
            创建项目
          </DialogTrigger>
          <DialogContent className="sm:max-w-[420px]">
            <DialogHeader>
              <DialogTitle>创建新项目</DialogTitle>
            </DialogHeader>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="project_name">项目名称</Label>
                <Input
                  id="project_name"
                  placeholder="例: DUS调度系统"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="root_path">项目根路径</Label>
                <Input
                  id="root_path"
                  placeholder="/Users/mac/Desktop/DUS"
                  value={rootPath}
                  onChange={(e) => setRootPath(e.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? "创建中..." : "创建"}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      ) : !projects?.length ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            暂无项目，点击右上角创建
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}
    </div>
  );
}
