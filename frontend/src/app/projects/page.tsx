"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchProjects, createProject } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
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

export default function ProjectsPage() {
  const [open, setOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [rootPath, setRootPath] = useState("");
  const queryClient = useQueryClient();

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
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
          <h2 className="text-2xl font-bold tracking-tight">项目管理</h2>
          <p className="text-muted-foreground">管理所有项目及其闲置状态</p>
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
                <Input id="project_name" placeholder="例: DUS调度系统" value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="root_path">项目根路径</Label>
                <Input id="root_path" placeholder="/Users/mac/Desktop/DUS" value={rootPath} onChange={(e) => setRootPath(e.target.value)} />
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

      <Card>
        <CardHeader>
          <CardTitle>项目列表</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">加载中...</p>
          ) : !projects?.length ? (
            <p className="text-sm text-muted-foreground">暂无项目，点击右上角创建</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>项目ID</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>根路径</TableHead>
                  <TableHead>闲置时长</TableHead>
                  <TableHead>闲置阈值</TableHead>
                  <TableHead>创建时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((p) => {
                  const isIdle =
                    p.idle_hours != null && p.idle_hours >= p.idle_threshold_hours;
                  return (
                    <TableRow key={p.id}>
                      <TableCell className="font-mono text-xs">
                        {p.project_id}
                      </TableCell>
                      <TableCell className="font-medium">
                        {p.project_name}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {p.root_path ?? "-"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={isIdle ? "destructive" : "default"}>
                          {p.idle_hours != null ? `${p.idle_hours}h` : "-"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {p.idle_threshold_hours}h
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTime(p.created_at)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
