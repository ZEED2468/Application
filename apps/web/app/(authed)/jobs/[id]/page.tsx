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
  Check,
  Eye,
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
import { formatDateTime, cn } from "@/lib/utils";
import { absoluteApiUrl } from "@/lib/api/client";
import { PageHeading, ErrorState } from "@/components/states";
import { PdfPreviewModal } from "@/components/pdf-preview-modal";
import { AtsBreakdown } from "@/components/ats-breakdown";
import { StatusCell } from "../status-cell";
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
  const [preview, setPreview] = React.useState<{ url: string; title: string } | null>(
    null,
  );

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
      toast.success("Generation started, refreshing");
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const applyMutation = useMutation({
    mutationFn: () => jobsService.apply(id),
    onSuccess: (res) => {
      if (res.apply_url) window.open(res.apply_url, "_blank", "noopener,noreferrer");
      toast.success(
        res.apply_url
          ? "Marked applied — opening the posting. Attach the CV/cover below."
          : "Marked applied. Attach the CV/cover below.",
      );
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

      <PdfPreviewModal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={preview?.title ?? ""}
        url={preview?.url}
      />

      <PageHeading
        title={job.role}
        description={`${job.company}${job.location ? ` · ${job.location}` : ""}`}
        actions={
          <div className="flex items-center gap-2">
            <Link href={`/jobs/${id}/builder`}>
              <Button variant="secondary">
                <FileText className="size-4" />
                LaTeX builder
              </Button>
            </Link>
            {!generated_cv ? (
              <Button
                variant="accent"
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
              >
                <Sparkles className="size-4" />
                {generateMutation.isPending ? "Generating…" : "Generate CV"}
              </Button>
            ) : !application ? (
              <Button
                variant="primary"
                onClick={() => applyMutation.mutate()}
                disabled={applyMutation.isPending}
              >
                <Send className="size-4" />
                {applyMutation.isPending ? "Applying…" : "Apply"}
              </Button>
            ) : (
              <Badge variant="default" className="px-3 py-1.5 text-sm">
                Applied
              </Badge>
            )}
          </div>
        }
      />

      <JobStepper
        current={application ? 3 : generated_cv ? 2 : job.status === "discovered" ? 0 : 1}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{TRACK_LABELS[job.track]}</Badge>
        <Badge variant={job.origin === "manual" ? "default" : "muted"}>
          {job.origin === "manual" ? "Manual" : "Auto"}
        </Badge>
        {application?.submitted_at && (
          <span className="text-xs text-coffee-400">
            Submitted {formatDateTime(application.submitted_at)}
          </span>
        )}
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
                Internal ATS match, optimized toward 90–95%. Not a guarantee in
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
          {/* Status */}
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
              <CardDescription>
                Update manually after applying, interviewing, or hearing back.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <StatusCell job={job} jobDetailId={id} />
            </CardContent>
          </Card>

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
              <DocRow
                label="Tailored CV"
                href={generated_cv?.download_url ?? null}
                onPreview={(u) =>
                  setPreview({ url: u, title: `Tailored CV — ${job.company}` })
                }
              />
              <DocRow
                label="Cover letter"
                href={cover_letter?.download_url ?? null}
                onPreview={(u) =>
                  setPreview({ url: u, title: `Cover letter — ${job.company}` })
                }
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
                  No application yet, generate to create one.
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

function JobStepper({ current }: { current: number }) {
  const steps = ["Discovered", "Tailored", "Ready", "Applied"];
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      {steps.map((s, i) => (
        <React.Fragment key={s}>
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2.5 py-1",
              i < current && "bg-coffee-100 text-coffee-500",
              i === current && "bg-coffee-700 font-medium text-cream",
              i > current && "border border-coffee-100 text-coffee-300",
            )}
          >
            {i < current && <Check className="size-3" />}
            {s}
          </span>
          {i < steps.length - 1 && <span className="h-px w-4 bg-coffee-200" />}
        </React.Fragment>
      ))}
    </div>
  );
}

function DocRow({
  label,
  href,
  onPreview,
}: {
  label: string;
  href: string | null;
  onPreview: (url: string) => void;
}) {
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
    <div className="flex items-center justify-between rounded-md border border-coffee-300 px-3 py-2.5">
      <span className="flex items-center gap-2 text-sm font-medium text-coffee-900">
        <FileText className="size-4 text-coffee-500" />
        {label}
      </span>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onPreview(href)}
          className="inline-flex items-center gap-1 text-xs text-coffee-700 underline underline-offset-2 hover:text-coffee-900"
        >
          <Eye className="size-3.5" />
          Preview
        </button>
        <a
          href={absoluteApiUrl(href) ?? "#"}
          target="_blank"
          rel="noreferrer noopener"
          className="text-xs text-coffee-500 underline underline-offset-2 hover:text-coffee-900"
        >
          Open
        </a>
      </div>
    </div>
  );
}
