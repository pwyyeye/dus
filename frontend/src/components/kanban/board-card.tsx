"use client";

import { useRouter } from "next/navigation";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PriorityPicker } from "./priority-picker";
import { EditIcon } from "lucide-react";
import type { Issue } from "@/lib/api";

const priorityConfig: Record<string, { label: string; color: string }> = {
  low: { label: "低", color: "text-muted-foreground" },
  medium: { label: "中", color: "text-blue-600" },
  high: { label: "高", color: "text-orange-600" },
  urgent: { label: "紧急", color: "text-red-600" },
};

interface BoardCardProps {
  issue: Issue;
  onPriorityChange: (issueId: string, priority: string) => void;
  onEdit?: (issue: Issue) => void;
}

export function BoardCard({ issue, onPriorityChange, onEdit }: BoardCardProps) {
  const router = useRouter();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: issue.id,
    data: { status: issue.status },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={isDragging ? "opacity-30" : ""}
    >
      <Card
        className="cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow"
        onClick={() => router.push(`/issues/${issue.id}`)}
      >
        <CardContent className="p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium line-clamp-2">{issue.title}</p>
            <div className="flex items-center gap-1 shrink-0">
              {onEdit && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => { e.stopPropagation(); onEdit(issue); }}
                  title="编辑"
                >
                  <EditIcon className="size-3.5" />
                </Button>
              )}
              <PriorityPicker
                priority={issue.priority}
                onChange={(priority) => onPriorityChange(issue.id, priority)}
              />
            </div>
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
    </div>
  );
}

/** Static card rendered inside DragOverlay (no sortable hooks) */
export function BoardCardOverlay({ issue }: { issue: Issue }) {
  const pConfig = priorityConfig[issue.priority] ?? { label: issue.priority, color: "" };

  return (
    <div className="w-[280px] rotate-2 scale-105 cursor-grabbing opacity-90 shadow-lg">
      <Card>
        <CardContent className="p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium line-clamp-2">{issue.title}</p>
            <span className={`text-xs font-medium ${pConfig.color}`}>{pConfig.label}</span>
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
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
