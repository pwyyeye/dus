"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from "@dnd-kit/core";
import { BoardColumn } from "./board-column";
import { BoardCardOverlay } from "./board-card";
import type { Issue } from "@/lib/api";

const COLUMNS = [
  { status: "backlog", label: "待规划", color: "border-t-gray-300" },
  { status: "todo", label: "待办", color: "border-t-gray-400" },
  { status: "in_progress", label: "进行中", color: "border-t-blue-500" },
  { status: "done", label: "已完成", color: "border-t-green-500" },
  { status: "blocked", label: "被阻塞", color: "border-t-orange-500" },
  { status: "cancelled", label: "已取消", color: "border-t-red-400" },
] as const;

const COLUMN_STATUSES = COLUMNS.map((c) => c.status);

function findColumn(columns: Record<string, string[]>, id: string): string | null {
  if (COLUMN_STATUSES.includes(id as typeof COLUMN_STATUSES[number])) return id;
  for (const [status, ids] of Object.entries(columns)) {
    if (ids.includes(id)) return status;
  }
  return null;
}

interface BoardViewProps {
  issues: Issue[];
  onStatusChange: (issueId: string, newStatus: string) => void;
  onPriorityChange: (issueId: string, priority: string) => void;
  onEdit?: (issue: Issue) => void;
  onViewTaskResult?: (issue: Issue) => void;
}

export function BoardView({ issues, onStatusChange, onPriorityChange, onEdit, onViewTaskResult }: BoardViewProps) {
  const [activeIssue, setActiveIssue] = useState<Issue | null>(null);

  // Local column state for optimistic drag feedback
  const [columns, setColumns] = useState<Record<string, string[]>>(() =>
    buildColumns(issues),
  );
  const columnsRef = useRef(columns);
  columnsRef.current = columns;

  const isDraggingRef = useRef(false);

  // Sync from props when not dragging
  useEffect(() => {
    if (!isDraggingRef.current) {
      setColumns(buildColumns(issues));
    }
  }, [issues]);

  // Issue lookup map, frozen during drag
  const issueMap = useRef(new Map<string, Issue>());
  if (!isDraggingRef.current) {
    const map = new Map<string, Issue>();
    for (const issue of issues) map.set(issue.id, issue);
    issueMap.current = map;
  }

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    isDraggingRef.current = true;
    const issue = issueMap.current.get(event.active.id as string) ?? null;
    setActiveIssue(issue);
  }, []);

  const handleDragOver = useCallback((event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    setColumns((prev) => {
      const activeCol = findColumn(prev, activeId);
      const overCol = findColumn(prev, overId);
      if (!activeCol || !overCol || activeCol === overCol) return prev;

      const oldIds = prev[activeCol].filter((id) => id !== activeId);
      const newIds = [...prev[overCol]];
      const overIndex = newIds.indexOf(overId);
      const insertIndex = overIndex >= 0 ? overIndex : newIds.length;
      newIds.splice(insertIndex, 0, activeId);
      return { ...prev, [activeCol]: oldIds, [overCol]: newIds };
    });
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      isDraggingRef.current = false;
      setActiveIssue(null);

      if (!over) {
        setColumns(buildColumns(issues));
        return;
      }

      const activeId = active.id as string;
      const overId = over.id as string;

      const cols = columnsRef.current;
      const activeCol = findColumn(cols, activeId);
      const overCol = findColumn(cols, overId);

      console.log("[DEBUG BoardView handleDragEnd] activeId=", activeId, "overId=", overId, "activeCol=", activeCol, "overCol=", overCol);

      if (!activeCol || !overCol) {
        setColumns(buildColumns(issues));
        return;
      }

      // Determine final column after cross-column drag
      const finalCol = findColumn(cols, activeId) ?? activeCol;

      // If the card moved to a different column, notify parent
      const currentIssue = issueMap.current.get(activeId);
      console.log("[DEBUG BoardView handleDragEnd] currentIssue=", currentIssue?.issue_id, "status=", currentIssue?.status, "finalCol=", finalCol);
      if (currentIssue && currentIssue.status !== finalCol) {
        console.log("[DEBUG BoardView] Calling onStatusChange:", activeId, finalCol);
        onStatusChange(activeId, finalCol);
      } else {
        // Same column — just reset to sort order
        setColumns(buildColumns(issues));
      }
    },
    [issues, onStatusChange],
  );

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLUMNS.map((col) => {
          const colIssueIds = columns[col.status] ?? [];
          const colIssues = colIssueIds
            .map((id) => issueMap.current.get(id))
            .filter((i): i is Issue => !!i);

          return (
            <BoardColumn
              key={col.status}
              status={col.status}
              label={col.label}
              color={col.color}
              issues={colIssues}
              onPriorityChange={onPriorityChange}
              onEdit={onEdit}
              onViewTaskResult={onViewTaskResult}
            />
          );
        })}
      </div>

      <DragOverlay dropAnimation={null}>
        {activeIssue ? <BoardCardOverlay issue={activeIssue} /> : null}
      </DragOverlay>
    </DndContext>
  );
}

function buildColumns(issues: Issue[]): Record<string, string[]> {
  const cols: Record<string, string[]> = {};
  for (const col of COLUMNS) {
    cols[col.status] = issues
      .filter((i) => i.status === col.status)
      .map((i) => i.id);
  }
  return cols;
}
