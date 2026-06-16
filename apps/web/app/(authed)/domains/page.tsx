"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe, PauseCircle } from "lucide-react";
import type { DomainHealth } from "@jd/shared-types";
import { adminService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS, WARMUP_LABELS } from "@/lib/status";
import { PageHeading, EmptyState, ErrorState } from "@/components/states";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

function Meter({
  value,
  max,
  tone = "coffee",
}: {
  value: number;
  max: number;
  tone?: "coffee" | "warn";
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-coffee-100">
      <div
        className={cn(
          "h-full rounded-full",
          pct >= 100 || tone === "warn"
            ? "bg-status-interviewed"
            : "bg-coffee-500",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function warmupBadgeVariant(d: DomainHealth) {
  if (d.paused) return "muted" as const;
  if (d.warmup_stage === "ready") return "default" as const;
  return "outline" as const;
}

export default function DomainsPage() {
  const domainsQuery = useQuery({
    queryKey: queryKeys.domains,
    queryFn: () => adminService.domains(),
  });
  const quotaQuery = useQuery({
    queryKey: queryKeys.quota,
    queryFn: () => adminService.quota(),
  });

  return (
    <div className="space-y-8">
      <PageHeading
        title="Domains"
        description="The nine sending domains' warm-up health and each hunter's weekly send quota. The warm-up governor protects deliverability in code — this panel is the read-out."
      />

      {/* Domain health */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-coffee-900">
          Domain health
        </h2>
        {domainsQuery.isError ? (
          <ErrorState
            description="Couldn't load domain health."
            retry={() => domainsQuery.refetch()}
          />
        ) : domainsQuery.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : (domainsQuery.data?.length ?? 0) === 0 ? (
          <EmptyState
            icon={<Globe className="size-8" />}
            title="No domains configured"
            description="Once sending domains are provisioned, their warm-up stage and deliverability appear here."
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {domainsQuery.data!.map((d) => (
              <Card key={d.id} className={cn(d.paused && "opacity-80")}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">{d.domain}</CardTitle>
                    {d.paused && (
                      <span className="inline-flex items-center gap-1 text-xs text-coffee-500">
                        <PauseCircle className="size-3.5" /> Paused
                      </span>
                    )}
                  </div>
                  <CardDescription>
                    {d.hunter_name} · {TRACK_LABELS[d.track]}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Badge variant={warmupBadgeVariant(d)}>
                      {WARMUP_LABELS[d.warmup_stage]}
                    </Badge>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-coffee-500">
                      <span>Sent today</span>
                      <span className="tabular-nums">
                        {d.sent_today} / {d.daily_cap}
                      </span>
                    </div>
                    <Meter value={d.sent_today} max={d.daily_cap} />
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-coffee-500">Bounce</p>
                      <p
                        className={cn(
                          "font-medium tabular-nums",
                          d.bounce_rate > 0.05
                            ? "text-status-rejected"
                            : "text-coffee-900",
                        )}
                      >
                        {(d.bounce_rate * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-coffee-500">Spam</p>
                      <p
                        className={cn(
                          "font-medium tabular-nums",
                          d.spam_rate > 0.02
                            ? "text-status-rejected"
                            : "text-coffee-900",
                        )}
                      >
                        {(d.spam_rate * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Quota */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-coffee-900">
          Per-hunter weekly quota
        </h2>
        {quotaQuery.isError ? (
          <ErrorState
            description="Couldn't load quota."
            retry={() => quotaQuery.refetch()}
          />
        ) : quotaQuery.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (quotaQuery.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="No quota data"
            description="Weekly send counts appear here once hunters start sending."
          />
        ) : (
          <Card>
            <CardContent className="space-y-5">
              {quotaQuery.data!.map((q) => (
                <div key={q.hunter_id} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-coffee-900">
                      {q.hunter_name}
                    </span>
                    <span className="tabular-nums text-coffee-500">
                      {q.sent_this_week} / {q.weekly_cap} this week
                    </span>
                  </div>
                  <Meter value={q.sent_this_week} max={q.weekly_cap} />
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
