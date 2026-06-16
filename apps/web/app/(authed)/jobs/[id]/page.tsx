"use client";

import * as React from "react";
import { use } from "react";
import Link from "next/link";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft,
  FileText,
  Sparkles,
  Send,
  Mail,
  History,
} from "lucide-react";
import type { JobDetail, Track } from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import {
  jobsService,
  applicationsService,
} from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import { PageHeading, ErrorState } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { AtsBreakdown } from "@/components/ats-breakdown";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export const dynamic = "force-dynamic";

export default function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const queryClient = useQueryClient();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.job(id),
    queryFn: () => jobsService.detail(id),
  });

  const audit = useQuery({
    queryKey: queryKeys.audit(data?.application?.id ?? ""),
    queryFn: () => applicationsService.audit(data!.application!.id),
    enabled: Boolean(data?.application?.id),
  });

  const trackMutation = useMutation({
    mutationFn: (track: Track) => jobsService.track(id, track),
    onSuccess: () => {
      toast.success("Track updated");
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const generateMutation = useMutation({
    mutationFn: () => jobsService.generate(id),
    onSuccess: () => {
      toast.success("Generation started — refreshing");
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const submitMutation = useMutation({
    mutationFn: () => jobsService.submit(id),
    onSuccess: () => {
      toast.success("Submitted to outreach");
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  if (isError) {
    return (
      <div className="space-y-6">
        <BackLink />
        <ErrorState
          title="Couldn't load this job"
          description="It may not exist, or the backend is offline."
          retry={() => refetch()}
        />
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <BackLink />
        <Skeleton className="h-10 w-72" />
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-64 lg:col-span-2" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  const { job, generated_cv, cover_letter, application, outreach, thread } =
    data;

  return (
    <div className="space-y-6">
      <BackLink />

      <PageHeading
        title={job.role}
        description={`${job.company}${job.location ? ` · ${job.location}` : ""}`}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="accent"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
            >
              <Sparkles className="size-4" />
              {generateMutation.isPending ? "Generating…" : "Generate"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => submitMutation.mutate()}
              disabled={submitMutation.isPending}
            >
              <Send className="size-4" />
              Submit
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{TRACK_LABELS[job.track]}</Badge>
        <Badge variant={job.origin === "manual" ? "default" : "muted"}>
          {job.origin === "manual" ? "Manual" : "Auto"}
        </Badge>
        {application && <StatusBadge status={application.status} />}
        {job.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-coffee-500 underline underline-offset-4 hover:text-coffee-700"
          >
            View original posting
          </a>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* JD */}
          <Card>
            <CardHeader>
              <CardTitle>Job description</CardTitle>
            </CardHeader>
            <CardContent>
              {job.jd_text || job.description ? (
                <p className="whitespace-pre-wrap text-[0.95rem] leading-relaxed text-coffee-700">
                  {job.jd_text ?? job.description}
                </p>
              ) : (
                <p className="text-coffee-300">
                  No job description on file for this role.
                </p>
              )}
            </CardContent>
          </Card>

          {/* ATS */}
          <Card>
            <CardHeader>
              <CardTitle>ATS match</CardTitle>
              <CardDescription>
                Internal ATS match — optimized toward 90–95%. Not a guarantee in
                any employer&apos;s applicant-tracking system.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AtsBreakdown
                score={generated_cv?.ats_score ?? null}
                breakdown={generated_cv?.ats_breakdown ?? null}
              />
            </CardContent>
          </Card>

          {/* Outreach thread */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="size-4 text-coffee-500" />
                Outreach
              </CardTitle>
              {outreach && (
                <CardDescription>
                  {outreach.contact_name
                    ? `To ${outreach.contact_name}${outreach.contact_title ? `, ${outreach.contact_title}` : ""} · `
                    : ""}
                  Step: {outreach.step} · {outreach.sent_count} sent
                </CardDescription>
              )}
            </CardHeader>
            <CardContent>
              {outreach?.company_hook && (
                <p className="mb-4 rounded-md border border-coffee-100 bg-coffee-100/40 px-3 py-2 text-sm text-coffee-700">
                  Hook: {outreach.company_hook}
                </p>
              )}
              {thread.length === 0 ? (
                <p className="text-coffee-300">
                  No messages yet. Submit to start first-contact outreach.
                </p>
              ) : (
                <ol className="space-y-4">
                  {thread.map((m) => (
                    <li
                      key={m.id}
                      className="rounded-md border border-coffee-100 px-4 py-3"
                    >
                      <div className="mb-1 flex items-center justify-between gap-2 text-xs text-coffee-500">
                        <span>
                          <Badge
                            variant={
                              m.direction === "inbound" ? "default" : "muted"
                            }
                          >
                            {m.direction === "inbound" ? "Reply" : "Sent"}
                          </Badge>{" "}
                          <span className="ml-1">
                            {m.from} → {m.to}
                          </span>
                        </span>
                        <span>{formatDateTime(m.sent_at)}</span>
                      </div>
                      {m.subject && (
                        <p className="text-sm font-medium text-coffee-900">
                          {m.subject}
                        </p>
                      )}
                      <p className="mt-1 whitespace-pre-wrap text-sm text-coffee-700">
                        {m.body}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Side column */}
        <div className="space-y-6">
          {/* Track override */}
          <Card>
            <CardHeader>
              <CardTitle>Track</CardTitle>
              <CardDescription>Override the classified track.</CardDescription>
            </CardHeader>
            <CardContent>
              <Select
                value={job.track}
                disabled={trackMutation.isPending}
                onChange={(e) =>
                  trackMutation.mutate(e.target.value as Track)
                }
              >
                {TRACKS.map((t) => (
                  <option key={t} value={t}>
                    {TRACK_LABELS[t]}
                  </option>
                ))}
              </Select>
            </CardContent>
          </Card>

          {/* Documents */}
          <Card>
            <CardHeader>
              <CardTitle>Documents</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <DocLink
                label="Tailored CV"
                href={generated_cv?.pdf_url ?? null}
              />
              <DocLink
                label="Cover letter"
                href={cover_letter?.pdf_url ?? null}
              />
            </CardContent>
          </Card>

          {/* Audit */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="size-4 text-coffee-500" />
                Audit trail
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!application ? (
                <p className="text-sm text-coffee-300">
                  No application yet — generate to create one.
                </p>
              ) : audit.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              ) : (audit.data?.length ?? 0) === 0 ? (
                <p className="text-sm text-coffee-300">No events recorded.</p>
              ) : (
                <ol className="space-y-3">
                  {audit.data!.map((ev) => (
                    <li key={ev.id} className="flex gap-3">
                      <span className="mt-1.5 size-2 shrink-0 rounded-full bg-coffee-300" />
                      <div>
                        <p className="text-sm text-coffee-900">{ev.message}</p>
                        <p className="text-xs text-coffee-300">
                          {ev.type} · {formatDateTime(ev.created_at)}
                          {ev.actor ? ` · ${ev.actor}` : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/jobs"
      className="inline-flex items-center gap-1.5 text-sm text-coffee-500 hover:text-coffee-700"
    >
      <ArrowLeft className="size-4" />
      Back to tracker
    </Link>
  );
}

function DocLink({ label, href }: { label: string; href: string | null }) {
  if (!href) {
    return (
      <div className="flex items-center justify-between rounded-md border border-coffee-100 px-3 py-2.5">
        <span className="flex items-center gap-2 text-sm text-coffee-300">
          <FileText className="size-4" />
          {label}
        </span>
        <span className="text-xs text-coffee-300">Not generated</span>
      </div>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="flex items-center justify-between rounded-md border border-coffee-300 px-3 py-2.5 transition-colors hover:bg-coffee-100"
    >
      <span className="flex items-center gap-2 text-sm font-medium text-coffee-900">
        <FileText className="size-4 text-coffee-500" />
        {label}
      </span>
      <span className="text-xs text-coffee-500">Open PDF</span>
    </a>
  );
}
