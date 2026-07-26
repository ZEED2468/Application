"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { tracksService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";

/** Persistent dashboard reminder for tracks that still need a resume. */
export function TrackReminder() {
  const { data } = useQuery({
    queryKey: queryKeys.tracks,
    queryFn: () => tracksService.list(),
    staleTime: 60_000,
  });
  const incomplete = (data ?? []).filter((t) => t.status === "setup_required");
  if (incomplete.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 rounded-md border border-status-interviewed/40 bg-status-interviewed/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="flex items-center gap-2 text-sm text-coffee-800">
        <AlertTriangle className="size-4 shrink-0 text-status-interviewed" />
        <span>
          <strong>{incomplete.length}</strong> track{incomplete.length > 1 ? "s" : ""} still
          need{incomplete.length > 1 ? "" : "s"} a resume before {incomplete.length > 1 ? "they" : "it"} can be used.
        </span>
      </p>
      <Link
        href="/profile"
        className="shrink-0 rounded-md border border-coffee-300 bg-white px-3 py-1.5 text-sm font-medium text-coffee-900 hover:bg-coffee-100"
      >
        Complete setup
      </Link>
    </div>
  );
}
