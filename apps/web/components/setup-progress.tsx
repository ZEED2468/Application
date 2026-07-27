"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, ArrowRight } from "lucide-react";
import { readinessService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";

/**
 * Dashboard onboarding banner — shows overall setup progress + the single next
 * recommended action, driven by the centralized readiness service. Hides itself
 * once setup is complete.
 */
export function SetupProgress() {
  const { data } = useQuery({
    queryKey: queryKeys.readiness,
    queryFn: () => readinessService.get(),
    staleTime: 60_000,
  });

  if (!data || data.complete) return null;
  const next = data.next_action;

  return (
    <div className="rounded-lg border border-coffee-300 bg-coffee-50/60 px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-medium text-coffee-900">
            <Sparkles className="size-4 text-coffee-500" />
            Finish setting up — {data.progress}% complete
          </p>
          {next && (
            <p className="mt-0.5 text-sm text-coffee-500">Next: {next.label}</p>
          )}
        </div>
        {next && (
          <Link
            href={next.action.route}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-coffee-700 px-3 py-1.5 text-sm font-medium text-cream hover:bg-coffee-900"
          >
            {next.action.label}
            <ArrowRight className="size-4" />
          </Link>
        )}
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-coffee-100">
        <div
          className="h-full rounded-full bg-status-offer transition-all"
          style={{ width: `${data.progress}%` }}
        />
      </div>
    </div>
  );
}
