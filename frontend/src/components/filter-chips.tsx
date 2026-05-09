"use client";

import { cn } from "@/lib/utils";

export interface FilterChip<T extends string = string> {
  value: T;
  label: string;
  count?: number;
  dot?: string; // CSS color class for the dot
}

interface FilterChipsProps<T extends string = string> {
  chips: FilterChip<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function FilterChips<T extends string>({
  chips,
  value,
  onChange,
  className,
}: FilterChipsProps<T>) {
  return (
    <div className={cn("flex items-center gap-1 flex-wrap", className)}>
      {chips.map((chip) => {
        const active = chip.value === value;
        return (
          <button
            key={chip.value}
            onClick={() => onChange(chip.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors",
              active
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {chip.dot && (
              <span
                className={cn("size-1.5 rounded-full", chip.dot)}
              />
            )}
            {chip.label}
            {chip.count !== undefined && (
              <span
                className={cn(
                  "ml-0.5 tabular-nums",
                  active ? "text-primary-foreground/80" : "text-muted-foreground/70"
                )}
              >
                {chip.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
