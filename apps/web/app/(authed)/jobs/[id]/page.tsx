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
  AlertTriangle,
  Check,
  ChevronRight,
  Eye,
  FileText,
  Sparkles,
  Send,
  Mail,
  History,
  Pencil,
  ExternalLink,
  UploadCloud,
  Wand2,
} from "lucide-react";
import type {
  GeneratedCv,
  JobDetail,
  Track,
  TrackReadiness,
} from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import {
  jobsService,
  applicationsService,
  atsService,
  cvRunsService,
  latexService,
} from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { formatDateTime, cn } from "@/lib/utils";
import { absoluteApiUrl } from "@/lib/api/client";
import { ErrorState } from "@/components/states";
import { SidePanel } from "@/components/ui/drawer";
import { AtsBreakdown } from "@/components/ats-breakdown";
import { FormatFixes } from "@/components/format-fixes";
import { ResumeEditor } from "@/components/resume-editor";
import { GapFiller } from "@/components/gap-filler-drawer";
import { StatusCell } from "../status-cell";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export const dynamic = "force-dynamic";

/** The single right-side panel content — one open at a time (split view). */
type Panel =
  | { kind: "keywords" }
  | { kind: "documents" }
  | { kind: "jd" }
  | { kind: "activity" }
  | { kind: "gaps" }
  | { kind: "fixes" };

const PANEL_TITLE: Record<Panel["kind"], string> = {
  keywords: "Keyword breakdown",
  documents: "Documents",
  jd: "Job description",
  activity: "Activity",
  gaps: "Close the gaps for this role",
  fixes: "Format check & fixes",
};

export default function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  // One side-panel open at a time. `lastPanel` retains the content through the close
  // animation so it doesn't blank out while sliding away.
  const [panel, setPanel] = React.useState<Panel | null>(null);
  const lastPanel = React.useRef<Panel | null>(null);
  if (panel) lastPanel.current = panel;
  const shownPanel = panel ?? lastPanel.current;
  // Bumped after a gap-filler regenerate so the résumé preview reloads the new PDF.
  const [refreshToken, setRefreshToken] = React.useState(0);

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

  // Deterministic, zero-LLM format check + fixes (the CV engine): compiles the CV, scores
  // it on the real PDF, and reports what it normalized. Opens the fixes panel on success.
  const formatMutation = useMutation({
    mutationFn: () => cvRunsService.runForJob(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
      setPanel({ kind: "fixes" });
    },
    onError: (err) => toastApiError(err, "Couldn't run the format check"),
  });

  // The cover letter used to be an information row that said "Not generated" and
  // offered nothing — the only route to one was Edit → Regenerate → Cover tab →
  // commit. This is that same pipeline behind one button, using the persisted ATS
  // recommendations for the job (the editor already works exactly this way).
  const coverMutation = useMutation({
    mutationFn: async () => {
      const job = data?.job;
      if (!job) throw new Error("Job not loaded");
      const recs = (await atsService.latestRecs(id)) ?? undefined;
      const res = await latexService.regenerate({
        job_id: id,
        track: job.track as Track,
        jd_text: job.jd_text ?? job.description ?? null,
        role_title: job.role,
        ats: recs,
      });
      if (!res.cover_latex?.trim()) {
        throw new Error(
          "No cover letter was produced — add a cover-letter template on your Profile.",
        );
      }
      return jobsService.setCoverFromLatex(id, res.cover_latex);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
      toast.success("Cover letter ready — preview it below.");
    },
    onError: (err) => toastApiError(err, "Couldn't generate the cover letter"),
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

      <header className="space-y-4 border-b border-coffee-200 pb-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight text-coffee-900">
              {job.role}
            </h1>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-coffee-500">
              <span className="font-medium text-coffee-700">{job.company}</span>
              {job.location && (
                <>
                  <span className="text-coffee-300">·</span>
                  <span>{job.location}</span>
                </>
              )}
              <span className="text-coffee-300">·</span>
              <span>
                {TRACK_LABELS[job.track as keyof typeof TRACK_LABELS] || job.track}
              </span>
              <span className="text-coffee-300">·</span>
              <span>{job.origin === "manual" ? "Manual" : "Auto"}</span>
              {job.url && (
                <>
                  <span className="text-coffee-300">·</span>
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 underline underline-offset-4 hover:text-coffee-700"
                  >
                    View posting <ExternalLink className="size-3" />
                  </a>
                </>
              )}
            </p>
          </div>
          <div className="shrink-0">
            {generated_cv && !application ? (
              <Button
                variant="primary"
                onClick={() => applyMutation.mutate()}
                disabled={applyMutation.isPending}
              >
                <Send className="size-4" />
                {applyMutation.isPending ? "Applying…" : "Apply"}
              </Button>
            ) : application ? (
              <Badge variant="solid" className="gap-1 px-3 py-1.5 text-sm">
                <Check className="size-3.5" /> Applied
              </Badge>
            ) : null}
          </div>
        </div>
        <JobStepper
          current={application ? 3 : generated_cv ? 2 : job.status === "discovered" ? 0 : 1}
        />
      </header>

      <div className="flex flex-col gap-6 xl:flex-row xl:items-start">
        {/* The résumé is the canvas — a fixed, always-full document. */}
        <div className="min-w-0 flex-1 xl:max-w-[46rem]">
          <ResumeHero
            id={id}
            company={job.company}
            status={job.status}
            hasApplication={Boolean(application)}
            generatedCv={generated_cv}
            generating={generateMutation.isPending}
            onGenerate={() => generateMutation.mutate(false)}
            refreshToken={refreshToken}
            readiness={data.readiness}
          />
        </div>

        {/* A compact context rail; heavy detail opens in the floating panel. */}
        <div className="w-full space-y-7 xl:w-[17rem] xl:shrink-0">
          {/* Ready to apply — the focal point of the rail */}
          <RailSection label="Ready to apply">
            <div className="space-y-3 rounded-lg border border-coffee-300 bg-white p-4 shadow-sm">
              {generated_cv ? (
                <>
                  <AtsBreakdown
                    variant="summary"
                    score={generated_cv.ats_score ?? null}
                    breakdown={generated_cv.ats_breakdown ?? null}
                  />
                  {generated_cv.ats_breakdown && (
                    <div className="space-y-2">
                      {generated_cv.ats_breakdown.missing_critical &&
                        generated_cv.ats_breakdown.missing_critical.length > 0 && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="w-full"
                            onClick={() => setPanel({ kind: "gaps" })}
                          >
                            <Sparkles className="size-4" />
                            Review{" "}
                            {generated_cv.ats_breakdown.missing_critical.length} gap
                            {generated_cv.ats_breakdown.missing_critical.length > 1
                              ? "s"
                              : ""}
                          </Button>
                        )}
                      <button
                        type="button"
                        onClick={() => setPanel({ kind: "keywords" })}
                        className="text-sm text-coffee-600 underline underline-offset-2 hover:text-coffee-900"
                      >
                        View keyword breakdown
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-coffee-500">
                  Generate the résumé to see its ATS readiness for this role.
                </p>
              )}

              {/* Deterministic format check + fixes (compiled artifact, zero LLM). */}
              <div className="border-t border-coffee-100 pt-3">
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  onClick={() =>
                    data.cv_run
                      ? setPanel({ kind: "fixes" })
                      : formatMutation.mutate()
                  }
                  disabled={formatMutation.isPending}
                >
                  <Wand2 className="size-4" />
                  {formatMutation.isPending
                    ? "Checking format…"
                    : data.cv_run
                      ? "View format fixes"
                      : "Check & fix format"}
                </Button>
                {data.cv_run && (
                  <button
                    type="button"
                    onClick={() => formatMutation.mutate()}
                    disabled={formatMutation.isPending}
                    className="mt-1.5 w-full text-center text-xs text-coffee-500 underline underline-offset-2 hover:text-coffee-800"
                  >
                    {data.cv_run.delta.fixed.length > 0
                      ? `${data.cv_run.delta.fixed.length} fix${data.cv_run.delta.fixed.length > 1 ? "es" : ""} applied`
                      : "No format issues"}{" "}
                    · re-run
                  </button>
                )}
              </div>
            </div>
          </RailSection>

          {/* Details — status + track as compact rows */}
          <RailSection label="Details">
            <div className="overflow-hidden rounded-lg border border-coffee-200 bg-white">
              <div className="flex items-center justify-between gap-3 px-4 py-3">
                <span className="text-sm text-coffee-600">Status</span>
                <StatusCell job={job} jobDetailId={id} />
              </div>
              <div className="flex items-center justify-between gap-3 border-t border-coffee-100 px-4 py-3">
                <span className="text-sm text-coffee-600">Track</span>
                <Select
                  value={job.track}
                  selectSize="sm"
                  disabled={trackMutation.isPending}
                  onChange={(e) => trackMutation.mutate(e.target.value as Track)}
                  className="w-40"
                >
                  {TRACKS.map((t) => (
                    <option key={t} value={t}>
                      {TRACK_LABELS[t]}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </RailSection>

          {/* More — everything heavy opens in the side-panel */}
          <RailSection label="More">
            <div className="overflow-hidden rounded-lg border border-coffee-200 bg-white">
              <button
                type="button"
                onClick={() => setPanel({ kind: "documents" })}
                className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm text-coffee-700 hover:bg-coffee-50"
              >
                <span className="flex items-center gap-2">
                  <FileText className="size-4 text-coffee-400" />
                  Documents
                </span>
                <ChevronRight className="size-4 text-coffee-400" />
              </button>
              <button
                type="button"
                onClick={() => setPanel({ kind: "jd" })}
                className="flex w-full items-center justify-between gap-2 border-t border-coffee-100 px-4 py-3 text-left text-sm text-coffee-700 hover:bg-coffee-50"
              >
                <span className="flex items-center gap-2">
                  <FileText className="size-4 text-coffee-400" />
                  Job description
                </span>
                <ChevronRight className="size-4 text-coffee-400" />
              </button>
              <button
                type="button"
                onClick={() => setPanel({ kind: "activity" })}
                className="flex w-full items-center justify-between gap-2 border-t border-coffee-100 px-4 py-3 text-left text-sm text-coffee-700 hover:bg-coffee-50"
              >
                <span className="flex items-center gap-2">
                  <History className="size-4 text-coffee-400" />
                  Activity{thread.length > 0 ? ` · ${thread.length}` : ""}
                </span>
                <ChevronRight className="size-4 text-coffee-400" />
              </button>
            </div>
          </RailSection>
        </div>
      </div>

      <SidePanel
        open={panel !== null}
        onClose={() => setPanel(null)}
        title={shownPanel ? PANEL_TITLE[shownPanel.kind] : ""}
        description={
          shownPanel?.kind === "jd" ? `${job.company} · ${job.role}` : undefined
        }
        width={
          shownPanel?.kind === "documents" || shownPanel?.kind === "keywords"
            ? "w-[42rem]"
            : "w-[34rem]"
        }
      >
        {shownPanel?.kind === "keywords" && (
          <AtsBreakdown
            variant="full"
            score={generated_cv?.ats_score ?? null}
            breakdown={generated_cv?.ats_breakdown ?? null}
          />
        )}

        {shownPanel?.kind === "fixes" &&
          (data.cv_run ? (
            <FormatFixes run={data.cv_run} />
          ) : (
            <p className="text-sm text-coffee-500">
              Run “Check &amp; fix format” to see the report.
            </p>
          ))}

        {shownPanel?.kind === "documents" && (
          <div className="space-y-6">
            <DocPanelItem
              label="Résumé"
              url={
                generated_cv?.download_url
                  ? absoluteApiUrl(generated_cv.download_url)
                  : null
              }
              empty="Generate the résumé first."
            />
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-coffee-900">Cover letter</h3>
                {generated_cv && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => coverMutation.mutate()}
                    disabled={coverMutation.isPending}
                  >
                    <Sparkles className="size-3.5" />
                    {coverMutation.isPending
                      ? "Writing…"
                      : cover_letter
                        ? "Regenerate"
                        : "Generate"}
                  </Button>
                )}
              </div>
              <DocPanelItem
                label="Cover letter"
                hideLabel
                url={
                  cover_letter?.download_url
                    ? absoluteApiUrl(cover_letter.download_url)
                    : null
                }
                empty={
                  generated_cv
                    ? "Generate the cover letter above."
                    : "Generate the résumé first."
                }
              />
            </div>
          </div>
        )}

        {shownPanel?.kind === "jd" && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-coffee-700">
            {jdText || "No job description on file."}
          </p>
        )}

        {shownPanel?.kind === "activity" && (
          <div className="space-y-6">
            <section className="space-y-2.5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-coffee-900">
                <Mail className="size-4 text-coffee-400" /> Outreach
              </h3>
              {outreach && (
                <p className="text-xs text-coffee-500">
                  {outreach.contact_name
                    ? `To ${outreach.contact_name}${outreach.contact_title ? `, ${outreach.contact_title}` : ""} · `
                    : ""}
                  Step: {outreach.step} · {outreach.sent_count} sent
                </p>
              )}
              {outreach?.company_hook && (
                <p className="rounded-md border border-coffee-100 bg-coffee-100/40 px-3 py-2 text-sm text-coffee-700">
                  Hook: {outreach.company_hook}
                </p>
              )}
              {thread.length === 0 ? (
                <p className="text-sm text-coffee-400">
                  No messages yet. Apply to start first-contact outreach.
                </p>
              ) : (
                <ol className="space-y-3">
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
            </section>

            <section className="space-y-2.5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-coffee-900">
                <History className="size-4 text-coffee-400" /> Audit trail
              </h3>
              {!application ? (
                <p className="text-sm text-coffee-400">
                  No application yet — apply to create one.
                </p>
              ) : audit.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              ) : (audit.data?.length ?? 0) === 0 ? (
                <p className="text-sm text-coffee-400">No events recorded.</p>
              ) : (
                <ol className="space-y-3">
                  {audit.data!.map((ev) => (
                    <li key={ev.id} className="flex gap-3">
                      <span className="mt-1.5 size-2 shrink-0 rounded-full bg-coffee-300" />
                      <div>
                        <p className="text-sm text-coffee-900">{ev.message}</p>
                        <p className="text-xs text-coffee-400">
                          {ev.type} · {formatDateTime(ev.created_at)}
                          {ev.actor ? ` · ${ev.actor}` : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        )}

        {shownPanel?.kind === "gaps" && (
          <GapFiller
            jobId={id}
            onClose={() => setPanel(null)}
            onRegenerated={() => setRefreshToken((t) => t + 1)}
          />
        )}
      </SidePanel>
    </div>
  );
}

/** A document row in the Documents panel: an inline PDF preview + a download/open link. */
function DocPanelItem({
  label,
  url,
  empty,
  hideLabel,
}: {
  label: string;
  url: string | null;
  empty: string;
  hideLabel?: boolean;
}) {
  return (
    <div className="space-y-2">
      {!hideLabel && (
        <h3 className="text-sm font-semibold text-coffee-900">{label}</h3>
      )}
      {url ? (
        <>
          <iframe
            src={url}
            title={label}
            className="h-[46vh] w-full rounded-md border border-coffee-200 bg-white"
          />
          <a
            href={url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 text-xs text-coffee-600 underline underline-offset-2 hover:text-coffee-900"
          >
            <ExternalLink className="size-3.5" /> Open in a new tab
          </a>
        </>
      ) : (
        <p className="text-sm text-coffee-400">{empty}</p>
      )}
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
  refreshToken,
  readiness,
}: {
  id: string;
  company: string;
  status: string;
  hasApplication: boolean;
  generatedCv: GeneratedCv | null;
  generating: boolean;
  onGenerate: () => void;
  refreshToken: number;
  readiness: TrackReadiness | null;
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
    <Card className="flex min-h-[78vh] flex-col shadow-sm">
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
          readiness && !readiness.ready ? (
            // Trust gate: this track has no readable CV, so we won't fabricate one —
            // tell the user exactly what's missing and where to fix it.
            <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-md border border-dashed border-status-interviewed/40 bg-status-interviewed/5 p-8 text-center">
              <div className="flex size-12 items-center justify-center rounded-full bg-status-interviewed/10 text-status-interviewed">
                <AlertTriangle className="size-6" />
              </div>
              <div className="space-y-1">
                <p className="text-base font-medium text-coffee-900">
                  {readiness.title ?? "Set up this track first"}
                </p>
                <p className="mx-auto max-w-sm text-sm text-coffee-600">
                  {readiness.message ??
                    "Upload a CV for this track so the résumé is tailored from your real experience."}
                </p>
              </div>
              {readiness.action && (
                <Link href={readiness.action.route}>
                  <Button variant="primary">
                    <UploadCloud className="size-4" />
                    {readiness.action.label}
                  </Button>
                </Link>
              )}
            </div>
          ) : (
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
          )
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
                key={`${docVersion}-${refreshToken}`}
                src={docUrl}
                title={`Tailored résumé — ${company}`}
                className="h-full min-h-[68vh] w-full rounded-md border border-coffee-200 bg-white"
              />
            ) : (
              <p className="text-sm text-coffee-400">Rendering…</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** A labelled rail group — an uppercase micro-label over its content. Turns the rail
 *  from a stack of equal cards into a few purposeful, scannable sections. */
function RailSection({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2.5">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-coffee-400">
        {label}
      </h2>
      {children}
    </section>
  );
}

function BackLink() {
  return (
    <Link
      href="/jobs"
      className="inline-flex items-center gap-1.5 text-sm text-coffee-500 hover:text-coffee-700"
    >
      <ArrowLeft className="size-4" />
      Back to jobs
    </Link>
  );
}

function JobStepper({ current }: { current: number }) {
  const steps = ["Discovered", "Tailored", "Ready", "Applied"];
  return (
    <div className="flex items-center">
      {steps.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <React.Fragment key={s}>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                  done && "bg-coffee-700 text-cream",
                  active && "bg-coffee-900 text-cream",
                  !done && !active && "border border-coffee-300 text-coffee-400",
                )}
              >
                {done ? <Check className="size-3" /> : i + 1}
              </span>
              <span
                className={cn(
                  "hidden text-xs sm:inline",
                  active
                    ? "font-medium text-coffee-900"
                    : done
                      ? "text-coffee-600"
                      : "text-coffee-400",
                )}
              >
                {s}
              </span>
            </div>
            {i < steps.length - 1 && (
              <span
                className={cn(
                  "mx-2 h-px flex-1 sm:mx-3",
                  done ? "bg-coffee-400" : "bg-coffee-200",
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

