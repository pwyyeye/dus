"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchInboxItems,
  markInboxRead,
  markAllInboxRead,
  deleteInboxItem,
  InboxItem,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BellIcon,
  CheckIcon,
  CheckCheckIcon,
  TrashIcon,
  AlertCircleIcon,
  InfoIcon,
} from "lucide-react";
import { toast } from "sonner";
import { SkeletonTable } from "@/components/ui/skeleton";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

const typeConfig: Record<string, { icon: string; color: string }> = {
  notification: { icon: "🔔", color: "bg-blue-100 text-blue-700" },
  alert: { icon: "⚠️", color: "bg-orange-100 text-orange-700" },
  info: { icon: "ℹ️", color: "bg-gray-100 text-gray-700" },
};

export default function InboxPage() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["inbox"],
    queryFn: () => fetchInboxItems({ limit: 100 }),
    refetchInterval: 30000,
  });

  const items = data?.items ?? [];

  const markReadMut = useMutation({
    mutationFn: markInboxRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      toast.success("已标记为已读");
    },
  });

  const markAllMut = useMutation({
    mutationFn: markAllInboxRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      toast.success("全部已读");
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteInboxItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
    },
  });

  const unreadCount = items.filter((i) => !i.is_read).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BellIcon className="size-6" />
            收件箱
          </h2>
          <p className="text-muted-foreground">
            {unreadCount > 0 ? `${unreadCount} 条未读消息` : "暂无未读消息"}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button
            variant="outline"
            onClick={() => markAllMut.mutate()}
            disabled={markAllMut.isPending}
          >
            <CheckCheckIcon className="size-4 mr-1" />
            全部已读
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <SkeletonTable rows={5} cols={3} />
          ) : items.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">收件箱为空</div>
          ) : (
            <div className="divide-y">
              {items.map((item: InboxItem) => {
                const config = typeConfig[item.item_type] ?? typeConfig.info;
                return (
                  <div
                    key={item.id}
                    className={`flex items-start gap-3 p-4 ${
                      !item.is_read ? "bg-muted/50" : ""
                    }`}
                  >
                    <span className="text-lg mt-0.5">{config.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className={`text-sm ${!item.is_read ? "font-semibold" : ""}`}>
                          {item.title}
                        </p>
                        {!item.is_read && (
                          <Badge variant="secondary" className="text-xs">
                            未读
                          </Badge>
                        )}
                      </div>
                      {item.message && (
                        <p className="text-sm text-muted-foreground mt-1">{item.message}</p>
                      )}
                      <p className="text-xs text-muted-foreground mt-1">
                        {formatTime(item.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {!item.is_read && (
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          title="标记已读"
                          onClick={() => markReadMut.mutate(item.id)}
                        >
                          <CheckIcon className="size-3.5" />
                        </Button>
                      )}
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        className="text-destructive"
                        title="删除"
                        onClick={() => deleteMut.mutate(item.id)}
                      >
                        <TrashIcon className="size-3.5" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
