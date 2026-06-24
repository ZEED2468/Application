"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  isLoading,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  isLoading?: boolean;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize && page <= 1) return null;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <div className="flex shrink-0 items-center justify-between border-t border-coffee-200 px-4 py-2.5 text-sm text-coffee-500">
      <span className="tabular-nums">
        {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          disabled={page <= 1 || isLoading}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft className="size-4" />
          Prev
        </Button>
        <span className="text-xs tabular-nums text-coffee-400">
          {page} / {pages}
        </span>
        <Button
          variant="ghost"
          size="sm"
          disabled={page >= pages || isLoading}
          onClick={() => onPage(page + 1)}
        >
          Next
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
