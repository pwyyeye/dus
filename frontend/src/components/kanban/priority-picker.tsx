"use client";

import { useState, useRef, useEffect } from "react";

const PRIORITIES: { value: string; label: string; color: string; bg: string }[] = [
  { value: "urgent", label: "紧急", color: "text-red-600", bg: "bg-red-50" },
  { value: "high", label: "高", color: "text-orange-600", bg: "bg-orange-50" },
  { value: "medium", label: "中", color: "text-blue-600", bg: "bg-blue-50" },
  { value: "low", label: "低", color: "text-muted-foreground", bg: "bg-gray-50" },
];

interface PriorityPickerProps {
  priority: string;
  onChange: (priority: string) => void;
}

export function PriorityPicker({ priority, onChange }: PriorityPickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = PRIORITIES.find((p) => p.value === priority) ?? PRIORITIES[2];

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${current.color} ${current.bg} hover:opacity-80 transition-opacity`}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen(!open);
        }}
        onMouseDown={(e) => {
          e.stopPropagation();
          e.preventDefault();
        }}
        onPointerDown={(e) => {
          e.stopPropagation();
        }}
      >
        {current.label}
      </button>
      {open && (
        <div
          className="absolute z-50 bottom-full left-0 mb-1 rounded-md border bg-popover shadow-md"
          onClick={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
        >
          {PRIORITIES.map((p) => (
            <button
              key={p.value}
              type="button"
              className={`flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-accent first:rounded-t-md last:rounded-b-md ${
                p.value === priority ? "bg-accent" : ""
              }`}
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                onChange(p.value);
                setOpen(false);
              }}
              onMouseDown={(e) => {
                e.stopPropagation();
                e.preventDefault();
              }}
            >
              <span className={`font-medium ${p.color}`}>{p.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
