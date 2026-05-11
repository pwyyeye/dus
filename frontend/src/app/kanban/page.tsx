"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchIssues, updateIssue } from "@/lib/api";
import { BoardView } from "@/components/kanban/board-view";
import { toast } from "sonner";

export default function KanbanPage() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["issues"],
    queryFn: () => fetchIssues({ limit: 200 }),
    refetchInterval: 15000,
  });

  const issues = data?.issues ?? [];

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateIssue(id, { status }),
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ["issues"] });
      const previous = queryClient.getQueryData(["issues"]);
      queryClient.setQueryData<{ issues: typeof issues; total: number }>(["issues"], (old) => {
        if (!old) return old;
        return {
          ...old,
          issues: old.issues.map((i) => (i.id === id ? { ...i, status: status as typeof i.status } : i)),
        };
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["issues"], context.previous);
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
      const previous = queryClient.getQueryData(["issues"]);
      queryClient.setQueryData<{ issues: typeof issues; total: number }>(["issues"], (old) => {
        if (!old) return old;
        return {
          ...old,
          issues: old.issues.map((i) => (i.id === id ? { ...i, priority: priority as typeof i.priority } : i)),
        };
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["issues"], context.previous);
      }
      toast.error("优先级更新失败");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">看板视图</h2>
        <p className="text-muted-foreground">拖拽卡片切换状态，点击优先级标签快速修改</p>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">加载中...</div>
      ) : (
        <BoardView
          issues={issues}
          onStatusChange={(id, status) => statusMutation.mutate({ id, status })}
          onPriorityChange={(id, priority) => priorityMutation.mutate({ id, priority })}
        />
      )}
    </div>
  );
}
