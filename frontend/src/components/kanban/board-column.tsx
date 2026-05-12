"use client";

import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { Badge } from "@/components/ui/badge";
import { BoardCard } from "./board-card";
import type { Issue } from "@/lib/api";

interface BoardColumnProps {
  status: string;
  label: string;
  color: string;
  issues: Issue[];
  onPriorityChange: (issueId: string, priority: string) => void;
  onEdit?: (issue: Issue) => void;
}

export function BoardColumn({ status, label, color, issues, onPriorityChange, onEdit }: BoardColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <div className="flex-1 min-w-[200px] max-w-[320px] space-y-3">
      <div className={`flex items-center gap-2 border-t-2 ${color} pt-2`}>
        <h3 className="text-sm font-medium">{label}</h3>
        <span className="text-xs text-muted-foreground bg-muted rounded-full px-1.5 py-0.5">
          {issues.length}
        </span>
      </div>
      <div
        ref={setNodeRef}
        className={`min-h-[200px] space-y-2 rounded-lg p-1 transition-colors ${
          isOver ? "bg-accent/40" : ""
        }`}
      >
        <SortableContext items={issues.map((i) => i.id)} strategy={verticalListSortingStrategy}>
          {issues.map((issue) => (
            <BoardCard
              key={issue.id}
              issue={issue}
              onPriorityChange={onPriorityChange}
              onEdit={onEdit}
            />
          ))}
        </SortableContext>
        {issues.length === 0 && (
          <p className="py-8 text-center text-xs text-muted-foreground">无</p>
        )}
      </div>
    </div>
  );
}
