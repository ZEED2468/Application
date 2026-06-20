"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Inbox, Send, MailCheck, MessageSquare } from "lucide-react";
import type { VaItemKind, VaQueueItem } from "@jd/shared-types";
import { vaService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import { PageHeading, EmptyState, ErrorState } from "@/components/states";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export const dynamic = "force-dynamic";

const KIND_META: Record<
  VaItemKind,
  { label: string; icon: React.ComponentType<{ className?: string }> }
> = {
  submit: { label: "To submit", icon: Send },
  outreach_review: { label: "Review outreach", icon: MailCheck },
  reply: { label: "Reply received", icon: MessageSquare },
};

const SECTION_ORDER: VaItemKind[] = ["submit", "outreach_review", "reply"];

export default function VaQueuePage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.vaQueue,
    queryFn: () => vaService.queue(),
  });

  const grouped = React.useMemo(() => {
    const map: Record<VaItemKind, VaQueueItem[]> = {
      submit: [],
      outreach_review: [],
      reply: [],
    };
    (data ?? []).forEach((item) => map[item.kind].push(item));
    return map;
  }, [data]);

  return (
    <div className="space-y-6">
      <PageHeading
        title="VA Queue"
        description="The human-in-the-loop desk, applications to submit, first-contact outreach to review before send, and replies to handle."
      />

      {isError ? (
        <ErrorState
          description="Couldn't load the queue. The backend may be offline."
          retry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : (data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={<Inbox className="size-8" />}
          title="Queue is clear"
          description="Nothing waiting right now. New items appear as applications are tailored and replies come in."
        />
      ) : (
        <div className="space-y-6">
          {SECTION_ORDER.map((kind) => {
            const items = grouped[kind];
            if (items.length === 0) return null;
            const Meta = KIND_META[kind];
            const Icon = Meta.icon;
            return (
              <Card key={kind}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Icon className="size-4 text-coffee-500" />
                    {Meta.label}
                    <Badge variant="muted">{items.length}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-col gap-2 rounded-md border border-coffee-100 p-4 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="font-medium text-coffee-900">
                          {item.role}{" "}
                          <span className="text-coffee-500">
                            · {item.company}
                          </span>
                        </p>
                        <p className="text-xs text-coffee-300">
                          {item.hunter_name} ·{" "}
                          {item.track in TRACK_LABELS
                            ? TRACK_LABELS[item.track]
                            : item.track}{" "}
                          · {formatDateTime(item.created_at)}
                        </p>
                        {item.preview && (
                          <p className="mt-1 line-clamp-2 text-sm text-coffee-700">
                            {item.preview}
                          </p>
                        )}
                      </div>
                      <Link href={`/jobs/${item.job_id}`}>
                        <Button size="sm" variant="secondary">
                          Open
                        </Button>
                      </Link>
                    </div>
                  ))}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
