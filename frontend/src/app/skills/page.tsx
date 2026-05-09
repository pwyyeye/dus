"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSkills,
  createSkill,
  deleteSkill,
  Skill,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
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
import { Badge } from "@/components/ui/badge";
import {
  PlusIcon,
  TrashIcon,
  CodeIcon,
  BrainIcon,
  DatabaseIcon,
  GlobeIcon,
} from "lucide-react";
import { toast } from "sonner";
import { SkeletonTable } from "@/components/ui/skeleton";

const categoryConfig: Record<string, { label: string; icon: string; color: string }> = {
  coding: { label: "编码", icon: "💻", color: "bg-blue-100 text-blue-700" },
  research: { label: "研究", icon: "🔍", color: "bg-purple-100 text-purple-700" },
  data: { label: "数据", icon: "📊", color: "bg-green-100 text-green-700" },
  web: { label: "Web", icon: "🌐", color: "bg-orange-100 text-orange-700" },
  other: { label: "其他", icon: "📦", color: "bg-gray-100 text-gray-700" },
};

export default function SkillsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  const { data: skills, isLoading } = useQuery({
    queryKey: ["skills", categoryFilter],
    queryFn: () => fetchSkills(categoryFilter ? { category: categoryFilter } : undefined),
  });

  const createMut = useMutation({
    mutationFn: createSkill,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      setOpen(false);
      toast.success("技能创建成功");
    },
    onError: (err: Error) => toast.error(`创建失败: ${err.message}`),
  });

  const deleteMut = useMutation({
    mutationFn: deleteSkill,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      toast.success("技能已删除");
    },
    onError: (err: Error) => toast.error(`删除失败: ${err.message}`),
  });

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const name = fd.get("name") as string;
    const description = fd.get("description") as string;
    const category = fd.get("category") as string;

    if (!name.trim()) return;

    createMut.mutate({
      name,
      description: description || undefined,
      category: category || undefined,
    });
    form.reset();
  };

  const categories = Object.entries(categoryConfig);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">技能管理</h2>
          <p className="text-muted-foreground">管理可复用的 Agent 技能</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <PlusIcon className="size-4 mr-1" />
          新建技能
        </Button>
      </div>

      <div className="flex gap-2">
        <Button
          variant={categoryFilter === "" ? "default" : "outline"}
          size="sm"
          onClick={() => setCategoryFilter("")}
        >
          全部
        </Button>
        {categories.map(([key, config]) => (
          <Button
            key={key}
            variant={categoryFilter === key ? "default" : "outline"}
            size="sm"
            onClick={() => setCategoryFilter(key)}
          >
            {config.icon} {config.label}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <SkeletonTable rows={4} cols={4} />
      ) : !skills || skills.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            暂无技能
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {skills.map((skill: Skill) => {
            const cat = categoryConfig[skill.category ?? "other"] ?? categoryConfig.other;
            return (
              <Card key={skill.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{cat.icon}</span>
                      <CardTitle className="text-base">{skill.name}</CardTitle>
                    </div>
                    <Button
                      size="icon-xs"
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => deleteMut.mutate(skill.id)}
                    >
                      <TrashIcon className="size-3.5" />
                    </Button>
                  </div>
                  {skill.category && (
                    <Badge variant="outline" className={`w-fit ${cat.color}`}>
                      {cat.label}
                    </Badge>
                  )}
                </CardHeader>
                <CardContent>
                  {skill.description ? (
                    <p className="text-sm text-muted-foreground">{skill.description}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">无描述</p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>新建技能</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="skill-name">名称</Label>
              <Input
                id="skill-name"
                name="name"
                placeholder="例如：python_expert"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="skill-desc">描述</Label>
              <Textarea
                id="skill-desc"
                name="description"
                placeholder="技能描述..."
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="skill-category">分类</Label>
              <Select name="category" defaultValue="">
                <SelectTrigger id="skill-category">
                  <SelectValue placeholder="选择分类" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">未分类</SelectItem>
                  {categories.map(([key, config]) => (
                    <SelectItem key={key} value={key}>
                      {config.icon} {config.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                取消
              </Button>
              <Button type="submit" disabled={createMut.isPending}>
                {createMut.isPending ? "创建中..." : "创建"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
