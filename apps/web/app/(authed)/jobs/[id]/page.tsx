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
  Pencil,
  ExternalLink,
} from "lucide-react";
import type { GeneratedCv, JobDetail, Track } from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import {
  jobsService,
  applicationsService,
} from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { formatDateTime, cn } from "@/lib/utils";
import { absoluteApiUrl } from "@/lib/api/client";
import { PageHeading, ErrorState } from "@/components/states";
import { PdfPreviewModal } from "@/components/pdf-preview-modal";
import { AtsBreakdown } from "@/components/ats-breakdown";
import { ResumeEditor } from "@/components/resume-editor";
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
  const [jdOpen, setJdOpen] = React.useState(false);

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
    mutationFn: (force: boolean) => jobsService.generate(id, force),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
      // The relevance prefilter skipped it as a low match — say so, and let the user
      // override instead of silently doing nothing.
      if (res.status === "rejected" && !res.generated_cv_id) {
        toast.error("Skipped — low match for your profile", {
          description:
            "This job scored below the relevance bar, so nothing was generated. Generate it anyway?",
          action: {
            label: "Generate anyway",
            onClick: () => generateMutation.mutate(true),
          },
        });
      } else {
        toast.success("Tailored CV generated.");
      }
    },
    onError: (err) => toastApiError(err),
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
    onError: (err) => toastApiError(err),
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
          <Skeleton className="h-[78vh] lg:col-span-2" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  const { job, generated_cv, cover_letter, application, outreach, thread } =
    data;
  const jdText = job.jd_text ?? job.description ?? "";

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
          // The résumé (centre) owns Generate + Edit; the header owns Apply once it exists.
          generated_cv && !application ? (
            <Button
              variant="primary"
              onClick={() => applyMutation.mutate()}
              disabled={applyMutation.isPending}
            >
              <Send className="size-4" />
              {applyMutation.isPending ? "Applying…" : "Apply"}
            </Button>
          ) : application ? (
            <Badge variant="default" className="px-3 py-1.5 text-sm">
              Applied
            </Badge>
          ) : undefined
        }
      />

      <JobStepper
        current={application ? 3 : generated_cv ? 2 : job.status === "discovered" ? 0 : 1}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">
          {TRACK_LABELS[job.track as keyof typeof TRACK_LABELS] || job.track}
        </Badge>
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
            className="inline-flex items-center gap-1 text-sm text-coffee-500 underline underline-offset-4 hover:text-coffee-700"
          >
            View original posting
            <ExternalLink className="size-3.5" />
          </a>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* The résumé is the workspace — centre stage. */}
        <div className="lg:col-span-2">
          <ResumeHero
            id={id}
            company={job.company}
            status={job.status}
            hasApplication={Boolean(application)}
            generatedCv={generated_cv}
            generating={generateMutation.isPending}
            onGenerate={() => generateMutation.mutate(false)}
          />
        </div>

        {/* Everything else supports the document, in a context rail. */}
        <div className="space-y-6">
          {/* Ready to apply? */}
          <Card>
            <CardHeader>
              <CardTitle>Ready to apply?</CardTitle>
              <CardDescription>
                Whether this résumé is ready — and what would make it readier.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AtsBreakdown
                variant="summary"
                detailsHref={`/ats-checker?job_id=${id}`}
                score={generated_cv?.ats_score ?? null}
                breakdown={generated_cv?.ats_breakdown ?? null}
              />
            </CardContent>
          </Card>

          {/* Job description (collapsible — the document, not the JD, leads) */}
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle>Job description</CardTitle>
              {jdText && (
                <button
                  type="button"
                  onClick={() => setJdOpen((o) => !o)}
                  className="text-xs text-coffee-500 hover:text-coffee-700"
                >
                  {jdOpen ? "Collapse" : "Expand"}
                </button>
              )}
            </CardHeader>
            <CardContent>
              {jdText ? (
                <p
                  className={cn(
                    "whitespace-pre-wrap text-sm leading-relaxed text-coffee-700",
                    !jdOpen && "line-clamp-6",
                  )}
                >
                  {jdText}
                </p>
              ) : (
                <p className="text-coffee-300">No job description on file.</p>
              )}
            </CardContent>
          </Card>

          {/* Cover letter (the CV is the hero; the cover lives here) */}
          <Card>
            <CardHeader>
              <CardTitle>Cover letter</CardTitle>
            </CardHeader>
            <CardContent>
              <DocRow
                label="Cover letter"
                href={cover_letter?.download_url ?? null}
                onPreview={(u) =>
                  setPreview({ url: u, title: `Cover letter — ${job.company}` })
                }
              />
            </CardContent>
          </Card>

          {/* Status */}
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
              <CardDescription>
                Update after applying, interviewing, or hearing back.
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
                onChange={(e) => trackMutation.mutate(e.target.value as Track)}
              >
                {TRACKS.map((t) => (
                  <option key={t} value={t}>
                    {TRACK_LABELS[t]}
                  </option>
                ))}
              </Select>
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
                <p className="text-sm text-coffee-300">
                  No messages yet. Apply to start first-contact outreach.
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
                            variant={m.direction === "inbound" ? "default" : "muted"}
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
                  No application yet — apply to create one.
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

/** The tailored résumé, centre stage. View mode renders the committed PDF; Edit swaps
 *  the same hero into the inline LaTeX editor (regenerate → tweak → commit) without ever
 *  leaving the workspace. Committing returns to a freshly-rendered view. */
function ResumeHero({
  id,
  company,
  status,
  hasApplication,
  generatedCv,
  generating,
  onGenerate,
}: {
  id: string;
  company: string;
  status: string;
  hasApplication: boolean;
  generatedCv: GeneratedCv | null;
  generating: boolean;
  onGenerate: () => void;
}) {
  // Deep links from "Regenerate CV" / the old builder route arrive as ?edit=…
  const [editing, setEditing] = React.useState(
    () =>
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("edit") != null,
  );
  // Bump on commit so the iframe remounts and re-fetches the updated PDF.
  const [docVersion, setDocVersion] = React.useState(0);

  const docUrl = generatedCv?.download_url
    ? absoluteApiUrl(generatedCv.download_url)
    : null;
  // A CV exists but the job never reached "ready" (e.g. render fell back / no compiler):
  // don't present a possibly-blank document as final.
  const notFullyRendered =
    Boolean(generatedCv) &&
    !hasApplication &&
    status !== "ready" &&
    status !== "submitted";

  return (
    <Card className="flex min-h-[78vh] flex-col">
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>{editing ? "Edit résumé" : "Tailored résumé"}</CardTitle>
        {editing ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setEditing(false)}
          >
            <Eye className="size-4" />
            Preview
          </Button>
        ) : (
          generatedCv && (
            <div className="flex shrink-0 items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setEditing(true)}
              >
                <Pencil className="size-4" />
                Edit
              </Button>
              {docUrl && (
                <a href={docUrl} target="_blank" rel="noreferrer noopener">
                  <Button variant="ghost" size="sm">
                    <ExternalLink className="size-4" />
                    Open
                  </Button>
                </a>
              )}
            </div>
          )
        )}
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {editing ? (
          <ResumeEditor
            id={id}
            onCommitted={() => {
              setEditing(false);
              setDocVersion((v) => v + 1);
            }}
          />
        ) : !generatedCv ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-md border border-dashed border-coffee-200 p-8 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-coffee-100 text-coffee-500">
              <FileText className="size-6" />
            </div>
            <div className="space-y-1">
              <p className="text-base font-medium text-coffee-900">
                Your tailored résumé will appear here
              </p>
              <p className="mx-auto max-w-sm text-sm text-coffee-500">
                Generate a truth-bounded CV for this role — rendered into your LaTeX
                template — then review it and apply.
              </p>
            </div>
            <Button variant="accent" onClick={onGenerate} disabled={generating}>
              <Sparkles className="size-4" />
              {generating ? "Generating…" : "Generate résumé"}
            </Button>
          </div>
        ) : (
          <div className="flex flex-1 flex-col gap-3">
            {notFullyRendered && (
              <p className="rounded-md border border-status-interviewed/40 bg-status-interviewed/5 px-3 py-2 text-sm text-coffee-800">
                This résumé couldn&apos;t be fully rendered yet — click Edit to fix and
                recompile it.
              </p>
            )}
            {docUrl ? (
              <iframe
                key={docVersion}
                src={docUrl}
                title={`Tailored résumé — ${company}`}
                className="h-full min-h-[68vh] w-full rounded-md border border-coffee-200 bg-white"
              />
            ) : (
              <p className="text-sm text-coffee-300">Rendering…</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
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
