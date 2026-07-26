"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface TabItem {
  value: string;
  label: React.ReactNode;
}

/** Minimal controlled tab bar (no external deps). Render the active panel yourself. */
export function Tabs({
  tabs,
  value,
  onValueChange,
  className,
}: {
  tabs: TabItem[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={cn("flex flex-wrap gap-1 border-b border-coffee-200", className)}
    >
      {tabs.map((t) => {
        const active = t.value === value;
        return (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onValueChange(t.value)}
            className={cn(
              "-mb-px rounded-t-md border-b-2 px-3 py-2 text-sm transition-colors",
              active
                ? "border-coffee-700 font-medium text-coffee-900"
                : "border-transparent text-coffee-500 hover:text-coffee-800",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
