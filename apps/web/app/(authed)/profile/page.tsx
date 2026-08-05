"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  UploadCloud,
  Check,
  FileText,
  Lock,
  Loader2,
  CheckCircle2,
  Settings,
} from "lucide-react";
import type {
  LatexKind,
  LatexTemplate,
  MasterProfile,
  MeResponse,
  Track,
} from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import { authService, onboardingService } from "@/lib/api/services";
import { absoluteApiUrl } from "@/lib/api/client";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { previewCoverLetterTemplate } from "@/lib/cover-letter-template";
import { PageHeading, EmptyState } from "@/components/states";
import { TracksManager } from "@/components/tracks-manager";
import { Accordion, type AccordionItemData } from "@/components/ui/accordion";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default function ProfilePage() {
  const queryClient = useQueryClient();
  // One active track at a time drives the whole page. `trackOverride` lets the
  // switcher feel instant before the /me mutation round-trips.
  const [trackOverride, setTrackOverride] = React.useState<Track | null>(null);
  const [showManage, setShowManage] = React.useState(false);
  // Optimistic per-track target-role counts so the guided flow advances to
  // "ready" the moment a first role is added — no profiles refetch needed.
  const [roleCounts, setRoleCounts] = React.useState<Partial<Record<Track, number>>>({});
  const [coverLetter, setCoverLetter] = React.useState("");
  const [templateFilename, setTemplateFilename] = React.useState<string | null>(
    null,
  );
  const [templateLoaded, setTemplateLoaded] = React.useState(false);

  const { data: me } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const profilesQuery = useQuery({
    queryKey: queryKeys.profiles,
    queryFn: () => onboardingService.profiles(),
  });

  const templateQuery = useQuery({
    queryKey: queryKeys.coverLetterTemplate,
    queryFn: () => onboardingService.getCoverLetterTemplate(),
    enabled: me?.type !== "va",
  });

  const latexTemplatesQuery = useQuery({
    queryKey: queryKeys.latexTemplates,
    queryFn: () => onboardingService.listLatexTemplates(),
    enabled: me?.type !== "va",
  });

  const latexByKey = React.useMemo(() => {
    const map = new Map<string, LatexTemplate>();
    (latexTemplatesQuery.data ?? []).forEach((t) =>
      map.set(`${t.track}:${t.kind}`, t),
    );
    return map;
  }, [latexTemplatesQuery.data]);

  React.useEffect(() => {
    if (templateLoaded || !templateQuery.data) return;
    setCoverLetter(templateQuery.data.body ?? "");
    setTemplateFilename(templateQuery.data.filename ?? null);
    setTemplateLoaded(true);
  }, [templateQuery.data, templateLoaded]);

  const previewText = React.useMemo(
    () =>
      previewCoverLetterTemplate(coverLetter, {
        name: me?.name ?? undefined,
      }),
    [coverLetter, me?.name],
  );

  const profileByTrack = React.useMemo(() => {
    const map = new Map<Track, MasterProfile>();
    (profilesQuery.data ?? []).forEach((p) => map.set(p.track, p));
    return map;
  }, [profilesQuery.data]);

  const trackKeys = React.useMemo(
    () => Array.from(profileByTrack.keys()),
    [profileByTrack],
  );
  const activeTrack: Track =
    trackOverride ?? me?.active_track ?? trackKeys[0] ?? TRACKS[0];
  const profile = profileByTrack.get(activeTrack);
  const label = TRACK_LABELS[activeTrack];

  // The guided flow's current step, derived from the confirm-gating chain.
  const rcv = profile?.role_cv;
  const rolesCount =
    roleCounts[activeTrack] ?? (profile?.target_roles?.length ?? 0);
  const step: "upload" | "reading" | "confirm" | "roles" | "ready" = !rcv
    ? "upload"
    : !rcv.parsed
      ? "reading"
      : !profile?.confirmed
        ? "confirm"
        : rolesCount === 0
          ? "roles"
          : "ready";
  const stepIndex =
    step === "upload"
      ? 0
      : step === "reading" || step === "confirm"
        ? 1
        : step === "roles"
          ? 2
          : 3;

  const uploadMutation = useMutation({
    mutationFn: ({ track, file }: { track: Track; file: File }) =>
      onboardingService.uploadRoleCv(track, file),
    onSuccess: (_data, vars) => {
      const structured = _data as {
        structured_by?: string;
        experience_entries?: number;
      };
      const detail =
        structured.structured_by === "llm"
          ? `Structured with AI (${structured.experience_entries ?? 0} experience blocks). Review and confirm.`
          : profileByTrack.get(vars.track)?.role_cv
            ? `${TRACK_LABELS[vars.track]} CV replaced — review and confirm again`
            : `${TRACK_LABELS[vars.track]} CV saved`;
      toast.success(detail);
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
    },
    onError: (err) => toastApiError(err),
  });

  const templateUploadMutation = useMutation({
    mutationFn: (file: File) => onboardingService.uploadCoverLetterTemplate(file),
    onSuccess: (data) => {
      toast.success("Cover-letter file uploaded — text loaded into the template");
      setCoverLetter(data.body ?? "");
      setTemplateFilename(data.filename ?? null);
      setTemplateLoaded(true);
      queryClient.invalidateQueries({ queryKey: queryKeys.coverLetterTemplate });
    },
    onError: (err) => toastApiError(err),
  });

  const templateMutation = useMutation({
    mutationFn: (body: string) =>
      onboardingService.setCoverLetterTemplate(body),
    onSuccess: (data) => {
      toast.success("Cover-letter template saved");
      setTemplateFilename(data.filename ?? null);
      queryClient.invalidateQueries({ queryKey: queryKeys.coverLetterTemplate });
    },
    onError: (err) => toastApiError(err),
  });

  const confirmMutation = useMutation({
    mutationFn: (track: Track) => onboardingService.confirm(track),
    onSuccess: (_d, track) => {
      toast.success(`${TRACK_LABELS[track]} profile confirmed`);
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
    },
    onError: (err) => toastApiError(err),
  });

  const activeTrackMutation = useMutation({
    mutationFn: (track: Track) => onboardingService.setActiveTrack(track),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.me }),
    onError: (err) => toastApiError(err),
  });

  function selectTrack(t: Track) {
    setTrackOverride(t);
    if (t !== me?.active_track) activeTrackMutation.mutate(t);
  }

  const coverDirty =
    templateLoaded &&
    coverLetter.trim() !== (templateQuery.data?.body ?? "").trim();

  if (me?.type === "va") {
    return (
      <EmptyState
        icon={<Lock className="size-8" />}
        title="Profile is hunter-only"
        description="Source CVs and cover-letter templates are managed by the hunter you assist."
      />
    );
  }

  const uploadBtn = (hasFile: boolean) => (
    <CvUploadButton
      track={activeTrack}
      hasFile={hasFile}
      isUploading={uploadMutation.isPending}
      onFile={(file) => uploadMutation.mutate({ track: activeTrack, file })}
    />
  );

  const coverLetterPanel = (
    <div className="space-y-5">
      <p className="text-sm text-coffee-500">
        Write a base cover letter, or upload one — use placeholders like{" "}
        {" {company} "}, {" {role} "} and {" {name} "}. Every application still
        gets its own tailored version; this is the starting point.
      </p>
      <div className="flex flex-col gap-3 rounded-md border border-coffee-100 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          {templateFilename ? (
            <span className="flex min-w-0 items-center gap-1.5 text-sm text-coffee-700">
              <FileText className="size-4 shrink-0 text-coffee-500" />
              <span className="truncate" title={templateFilename}>
                {templateFilename}
              </span>
              <a
                href={absoluteApiUrl("/api/onboarding/cover-letter-template/file") ?? "#"}
                target="_blank"
                rel="noreferrer noopener"
                className="shrink-0 text-xs text-coffee-500 underline underline-offset-2 hover:text-coffee-900"
              >
                Download
              </a>
            </span>
          ) : (
            <span className="text-sm text-coffee-300">No file uploaded yet</span>
          )}
        </div>
        <label className="inline-flex shrink-0 cursor-pointer items-center gap-2 rounded-md border border-coffee-300 px-3 py-1.5 text-sm text-coffee-700 transition-colors hover:bg-coffee-100">
          <UploadCloud className="size-4" />
          {templateFilename ? "Replace file" : "Upload file"}
          <input
            type="file"
            accept=".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            className="hidden"
            disabled={templateUploadMutation.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) templateUploadMutation.mutate(file);
              e.target.value = "";
            }}
          />
        </label>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="cover">Template body</Label>
          {templateQuery.isLoading ? (
            <Skeleton className="min-h-52 w-full" />
          ) : (
            <Textarea
              id="cover"
              value={coverLetter}
              onChange={(e) => setCoverLetter(e.target.value)}
              placeholder="Dear {company} team, I'm excited about the {role} role…"
              className="min-h-52 font-mono text-sm leading-relaxed"
            />
          )}
        </div>
        <div className="space-y-1.5">
          <Label>Preview</Label>
          <div className="min-h-52 rounded-md border border-coffee-200 bg-coffee-50/40 px-4 py-3">
            {previewText ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-coffee-800">
                {previewText}
              </p>
            ) : (
              <p className="text-sm text-coffee-300">
                Your preview appears here as you type or upload a file.
              </p>
            )}
          </div>
          <p className="text-xs text-coffee-400">
            Sample values: Acme Corp · Senior Engineer · your first name.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3">
        {coverDirty && (
          <span className="text-xs text-status-interviewed">Unsaved changes</span>
        )}
        <Button
          variant="secondary"
          disabled={templateMutation.isPending || coverLetter.trim().length === 0}
          onClick={() => templateMutation.mutate(coverLetter)}
        >
          Save template
        </Button>
      </div>
    </div>
  );

  const refineItems: AccordionItemData[] = profile
    ? [
        {
          id: "skills",
          title: "Skills & things you've done",
          content: (
            <div className="space-y-5">
              <PreferredSkillsEditor
                track={activeTrack}
                initial={profile.preferred_skills ?? []}
              />
              <VerifiedExtrasEditor
                track={activeTrack}
                initial={profile.verified_extras ?? {}}
              />
            </div>
          ),
        },
        {
          id: "design",
          title: "Your résumé design (optional)",
          content: (
            <div className="space-y-3">
              <p className="text-sm text-coffee-500">
                Upload your own CV / cover-letter design and your tailored,
                truthful content is rendered into it. Leave empty to use the
                clean built-in layout.
              </p>
              <div className="grid gap-6 lg:grid-cols-2">
                <LatexTemplateField
                  track={activeTrack}
                  kind="cv"
                  initial={latexByKey.get(`${activeTrack}:cv`)}
                />
                <LatexTemplateField
                  track={activeTrack}
                  kind="cover"
                  initial={latexByKey.get(`${activeTrack}:cover`)}
                />
              </div>
            </div>
          ),
        },
        {
          id: "cover",
          title: "Cover-letter template",
          content: coverLetterPanel,
        },
        {
          id: "prefs",
          title: "Preferences — links, locations, salary",
          content: <CareerDetailsEditor key={activeTrack} track={activeTrack} initial={profile} />,
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      <PageHeading
        title="Profile"
        description="One track at a time: upload your CV, confirm it, add your target roles. Refine the rest whenever you like."
      />

      {/* Track switcher — the single control for which track you're setting up */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-lg border border-coffee-300 bg-white px-5 py-4">
        <div className="flex items-center gap-2.5">
          <Label htmlFor="active-track" className="text-coffee-500">
            Setting up
          </Label>
          <select
            id="active-track"
            value={activeTrack}
            onChange={(e) => selectTrack(e.target.value as Track)}
            disabled={activeTrackMutation.isPending}
            className="h-9 rounded-md border border-coffee-300 bg-white px-2.5 text-sm font-medium text-coffee-900"
          >
            {TRACKS.map((t) => (
              <option key={t} value={t}>
                {TRACK_LABELS[t]}
                {profileByTrack.get(t)?.confirmed ? " ✓" : ""}
              </option>
            ))}
          </select>
        </div>
        <span className="text-xs text-coffee-400">
          drives which jobs &amp; templates your dashboard prioritizes
        </span>
        <button
          type="button"
          onClick={() => setShowManage((v) => !v)}
          className="ml-auto inline-flex items-center gap-1.5 text-sm text-coffee-600 hover:text-coffee-900"
        >
          <Settings className="size-4" />
          Manage tracks
        </button>
      </div>

      {showManage && <TracksManager />}

      {/* Guided primary flow */}
      <Card>
        <CardHeader>
          <CardTitle>Set up your {label} profile</CardTitle>
          <div className="pt-2">
            <StepIndicator stepIndex={stepIndex} />
          </div>
        </CardHeader>
        <CardContent>
          {profilesQuery.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : step === "upload" ? (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <div className="flex size-14 items-center justify-center rounded-full bg-coffee-100 text-coffee-600">
                <UploadCloud className="size-7" />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-semibold text-coffee-900">
                  Upload your CV for {label}
                </h3>
                <p className="mx-auto max-w-md text-sm text-coffee-500">
                  We&apos;ll read it and build your {label} profile — one file to
                  get started. PDF or Word.
                </p>
              </div>
              {uploadBtn(false)}
            </div>
          ) : step === "reading" ? (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <Loader2 className="size-8 animate-spin text-coffee-500" />
              <div className="space-y-1">
                <h3 className="text-lg font-semibold text-coffee-900">
                  Reading your CV…
                </h3>
                <p className="mx-auto max-w-md text-sm text-coffee-500">
                  Extracting your skills and experience
                  {rcv?.filename ? ` from ${rcv.filename}` : ""}. This only takes
                  a moment — refresh if it doesn&apos;t update.
                </p>
              </div>
              {uploadBtn(true)}
            </div>
          ) : step === "confirm" ? (
            <div className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-1">
                  <h3 className="text-lg font-semibold text-coffee-900">
                    Review what we read
                  </h3>
                  <p className="text-sm text-coffee-500">
                    {rcv?.filename ? `From ${rcv.filename}. ` : ""}Confirm it
                    looks right — you can refine the details below anytime.
                  </p>
                </div>
                {uploadBtn(true)}
              </div>
              <div className="space-y-3 rounded-md border border-coffee-100 bg-coffee-50/40 p-4">
                {profile?.headline && (
                  <p className="font-medium text-coffee-900">{profile.headline}</p>
                )}
                {profile?.summary && (
                  <p className="text-sm leading-relaxed text-coffee-700">
                    {profile.summary}
                  </p>
                )}
                {(profile?.skills?.length ?? 0) > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {(profile?.skills ?? []).slice(0, 14).map((s) => (
                      <Badge key={s} variant="outline">
                        {s}
                      </Badge>
                    ))}
                    {(profile?.skills?.length ?? 0) > 14 && (
                      <span className="self-center text-xs text-coffee-400">
                        +{(profile?.skills?.length ?? 0) - 14} more
                      </span>
                    )}
                  </div>
                ) : (
                  !profile?.headline &&
                  !profile?.summary && (
                    <p className="text-sm text-coffee-500">
                      Your file is saved. Confirm to continue, then add your
                      skills below.
                    </p>
                  )
                )}
              </div>
              <div className="flex justify-end">
                <Button
                  disabled={confirmMutation.isPending}
                  onClick={() => confirmMutation.mutate(activeTrack)}
                >
                  <Check className="size-4" />
                  Looks right — confirm
                </Button>
              </div>
            </div>
          ) : (
            /* roles + ready share the mounted TargetRolesEditor */
            <div className="space-y-4">
              {step === "roles" ? (
                <div className="space-y-1">
                  <h3 className="text-lg font-semibold text-coffee-900">
                    What roles are you targeting?
                  </h3>
                  <p className="text-sm text-coffee-500">
                    Add the roles you want. Job discovery only surfaces scraped
                    jobs whose title matches one of these.
                  </p>
                </div>
              ) : (
                <div className="flex items-start gap-3 rounded-md border border-coffee-200 bg-coffee-50 p-4">
                  <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-status-offer" />
                  <div className="space-y-0.5">
                    <p className="font-medium text-coffee-900">
                      You&apos;re set for {label}
                    </p>
                    <p className="text-sm text-coffee-600">
                      CV confirmed · {rolesCount} target role
                      {rolesCount === 1 ? "" : "s"} ·{" "}
                      {profile?.latex_cv
                        ? "custom résumé design"
                        : "built-in résumé layout"}
                      . Refine anything below.
                    </p>
                  </div>
                </div>
              )}
              <TargetRolesEditor
                track={activeTrack}
                initial={profile?.target_roles ?? []}
                onCountChange={(n) =>
                  setRoleCounts((c) => ({ ...c, [activeTrack]: n }))
                }
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Progressive disclosure — everything optional, closed by default */}
      {profile && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-coffee-400">
            Refine your {label} profile
          </h2>
          <Accordion items={refineItems} />
        </div>
      )}
    </div>
  );
}

/** Compact Upload → Confirm → Target roles progress for the guided flow. */
function StepIndicator({ stepIndex }: { stepIndex: number }) {
  const steps = ["Upload CV", "Confirm", "Target roles"];
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      {steps.map((s, i) => {
        const done = stepIndex > i;
        const current = stepIndex === i;
        return (
          <li key={s} className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex size-5 items-center justify-center rounded-full border text-[0.7rem] font-semibold",
                done
                  ? "border-status-offer bg-status-offer text-white"
                  : current
                    ? "border-coffee-700 text-coffee-800"
                    : "border-coffee-200 text-coffee-300",
              )}
            >
              {done ? <Check className="size-3" /> : i + 1}
            </span>
            <span
              className={cn(
                done
                  ? "text-coffee-500"
                  : current
                    ? "font-medium text-coffee-800"
                    : "text-coffee-300",
              )}
            >
              {s}
            </span>
            {i < steps.length - 1 && (
              <span className="mx-1 hidden h-px w-6 bg-coffee-200 sm:block" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Plain-language ATS format-gate note from the trial compile done at save time —
 * so a two-column / non-compiling template is legible here, not a surprise at export. */
function GateNote({ gate }: { gate: NonNullable<LatexTemplate["gate"]> }) {
  const reasons = Array.isArray((gate as { reasons?: unknown }).reasons)
    ? ((gate as { reasons?: string[] }).reasons ?? [])
    : [];
  if (gate.status === "pass") {
    return (
      <p className="text-xs text-status-offer">
        ✓ Compiles cleanly — your tailored content will render in this design.
      </p>
    );
  }
  if (gate.status === "fail") {
    return (
      <p className="text-xs text-status-interviewed">
        ⚠ This template couldn’t be compiled, so regeneration falls back to the built-in
        layout{reasons.length > 0 ? `: ${reasons.join("; ")}` : ""}.
      </p>
    );
  }
  return (
    <p className="text-xs text-coffee-400">Format check unavailable in this environment.</p>
  );
}

function LatexTemplateField({
  track,
  kind,
  initial,
}: {
  track: Track;
  kind: LatexKind;
  initial?: LatexTemplate;
}) {
  const queryClient = useQueryClient();
  const [source, setSource] = React.useState(initial?.source ?? "");
  const [filename, setFilename] = React.useState<string | null>(
    initial?.filename ?? null,
  );
  const inputRef = React.useRef<HTMLInputElement>(null);
  const syncKey = `${initial?.has_source ?? false}:${initial?.filename ?? ""}`;
  React.useEffect(() => {
    setSource(initial?.source ?? "");
    setFilename(initial?.filename ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncKey]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.latexTemplates });
    queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
  };

  const upload = useMutation({
    mutationFn: (file: File) =>
      onboardingService.uploadLatexTemplate(track, kind, file),
    onSuccess: (data) => {
      setSource(data.source ?? "");
      setFilename(data.filename ?? null);
      toast.success(`${kind === "cv" ? "CV" : "Cover-letter"} LaTeX uploaded`);
      invalidate();
    },
    onError: (err) => toastApiError(err),
  });

  const save = useMutation({
    mutationFn: () => onboardingService.setLatexTemplate(track, kind, source),
    onSuccess: () => {
      toast.success("LaTeX template saved");
      invalidate();
    },
    onError: (err) => toastApiError(err),
  });

  const dirty = source !== (initial?.source ?? "");

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <Label>
          {kind === "cv" ? "CV template (.tex)" : "Cover-letter template (.tex)"}
        </Label>
        <div className="flex shrink-0 items-center gap-2">
          {filename && (
            <a
              href={
                absoluteApiUrl(
                  `/api/onboarding/latex-template/${track}/${kind}/file`,
                ) ?? "#"
              }
              target="_blank"
              rel="noreferrer noopener"
              className="text-xs text-coffee-500 underline underline-offset-2 hover:text-coffee-900"
            >
              Download
            </a>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".tex,.txt,text/plain,application/x-tex"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
              e.target.value = "";
            }}
          />
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={upload.isPending}
            onClick={() => inputRef.current?.click()}
          >
            <UploadCloud className="size-4" />
            {filename ? "Replace" : "Upload .tex"}
          </Button>
        </div>
      </div>
      <Textarea
        value={source}
        onChange={(e) => setSource(e.target.value)}
        spellCheck={false}
        placeholder={"\\documentclass{article}\n…your LaTeX skeleton"}
        className="min-h-40 font-mono text-xs leading-relaxed"
      />
      <div className="flex items-center justify-end gap-3">
        {dirty && (
          <span className="text-xs text-status-interviewed">Unsaved changes</span>
        )}
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={save.isPending || source.trim().length === 0}
          onClick={() => save.mutate()}
        >
          Save
        </Button>
      </div>
      {initial?.gate && <GateNote gate={initial.gate} />}
    </div>
  );
}

const CV_ACCEPT =
  ".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function CvUploadButton({
  track,
  hasFile,
  isUploading,
  onFile,
}: {
  track: Track;
  hasFile: boolean;
  isUploading: boolean;
  onFile: (file: File) => void;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={CV_ACCEPT}
        className="hidden"
        aria-label={`Upload CV for ${TRACK_LABELS[track]}`}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
      <Button
        type="button"
        size="sm"
        variant={hasFile ? "secondary" : "primary"}
        disabled={isUploading}
        onClick={() => inputRef.current?.click()}
      >
        <UploadCloud className="size-4" />
        {isUploading ? "Uploading…" : hasFile ? "Replace file" : "Upload file"}
      </Button>
    </>
  );
}

function TargetRolesEditor({
  track,
  initial,
  onCountChange,
}: {
  track: Track;
  initial: string[];
  onCountChange?: (count: number) => void;
}) {
  const [roles, setRoles] = React.useState<string[]>(initial);
  const [input, setInput] = React.useState("");
  const key = initial.join("|");
  React.useEffect(() => {
    setRoles(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const save = useMutation({
    mutationFn: (next: string[]) => onboardingService.setTargetRoles(track, next),
    onSuccess: (res) => {
      setRoles(res.target_roles);
      onCountChange?.(res.target_roles.length);
    },
    onError: (err) => toastApiError(err),
  });

  function add() {
    const v = input.trim();
    setInput("");
    if (!v || roles.includes(v)) return;
    const next = [...roles, v];
    setRoles(next);
    onCountChange?.(next.length);
    save.mutate(next);
  }
  function remove(r: string) {
    const next = roles.filter((x) => x !== r);
    setRoles(next);
    onCountChange?.(next.length);
    save.mutate(next);
  }

  return (
    <div className="space-y-2">
      <Label>Target roles</Label>
      <p className="text-xs text-coffee-500">
        We only surface scraped jobs whose title matches one of these. Leave empty
        to see every job for this track.
      </p>
      {roles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {roles.map((r) => (
            <span
              key={r}
              className="inline-flex items-center gap-1.5 rounded-full border border-coffee-300 bg-coffee-100 px-2.5 py-1 text-xs text-coffee-800"
            >
              {r}
              <button
                type="button"
                onClick={() => remove(r)}
                aria-label={`Remove ${r}`}
                className="text-coffee-500 hover:text-coffee-900"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder="e.g. Senior React Engineer"
        />
        <Button
          type="button"
          variant="secondary"
          disabled={save.isPending || input.trim().length === 0}
          onClick={add}
        >
          Add
        </Button>
      </div>
    </div>
  );
}

function ChipField({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = React.useState("");
  function add() {
    const v = input.trim();
    setInput("");
    if (!v || values.includes(v)) return;
    onChange([...values, v]);
  }
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {values.map((r) => (
            <span
              key={r}
              className="inline-flex items-center gap-1.5 rounded-full border border-coffee-300 bg-coffee-100 px-2.5 py-1 text-xs text-coffee-800"
            >
              {r}
              <button
                type="button"
                onClick={() => onChange(values.filter((x) => x !== r))}
                aria-label={`Remove ${r}`}
                className="text-coffee-500 hover:text-coffee-900"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
        />
        <Button
          type="button"
          variant="secondary"
          disabled={input.trim().length === 0}
          onClick={add}
        >
          Add
        </Button>
      </div>
    </div>
  );
}

function PreferredSkillsEditor({ track, initial }: { track: Track; initial: string[] }) {
  const [values, setValues] = React.useState<string[]>(initial);
  const key = initial.join("|");
  React.useEffect(() => {
    setValues(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const save = useMutation({
    mutationFn: (next: string[]) => onboardingService.setPreferences(track, next),
    onError: (err) => toastApiError(err),
  });
  function update(next: string[]) {
    setValues(next);
    save.mutate(next);
  }
  return (
    <ChipField
      label="Skills to emphasize when tailoring"
      values={values}
      onChange={update}
      placeholder="e.g. Kafka"
    />
  );
}

const EXTRA_CATEGORIES: { key: string; label: string }[] = [
  { key: "frameworks", label: "Frameworks" },
  { key: "tools", label: "Tools" },
  { key: "methodologies", label: "Methodologies" },
  { key: "certifications", label: "Certifications" },
  { key: "coursework", label: "Coursework" },
  { key: "open_source", label: "Open source" },
  { key: "side_projects", label: "Side projects" },
  { key: "languages", label: "Languages" },
];

function VerifiedExtrasEditor({
  track,
  initial,
}: {
  track: Track;
  initial: Record<string, string[]>;
}) {
  const [extras, setExtras] = React.useState<Record<string, string[]>>(initial);
  const key = JSON.stringify(initial);
  React.useEffect(() => {
    setExtras(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const save = useMutation({
    mutationFn: (next: Record<string, string[]>) =>
      onboardingService.setVerifiedExtras(track, next),
    onError: (err) => toastApiError(err),
  });
  function update(cat: string, next: string[]) {
    const merged = { ...extras, [cat]: next };
    setExtras(merged);
    save.mutate(merged);
  }
  return (
    <div className="space-y-3 border-t border-coffee-100 pt-4">
      <div>
        <Label>Things you&apos;ve genuinely done (not on your CV)</Label>
        <p className="text-xs text-coffee-500">
          Add real skills, tools and projects the CV left out — the AI can surface
          these when tailoring. Only add what&apos;s true.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {EXTRA_CATEGORIES.map((c) => (
          <ChipField
            key={c.key}
            label={c.label}
            values={extras[c.key] ?? []}
            onChange={(next) => update(c.key, next)}
            placeholder={`Add ${c.label.toLowerCase()}…`}
          />
        ))}
      </div>
    </div>
  );
}

function CareerDetailsEditor({ track, initial }: { track: Track; initial: MasterProfile }) {
  const links = initial.links ?? {};
  const [linkedin, setLinkedin] = React.useState(links.linkedin ?? "");
  const [github, setGithub] = React.useState(links.github ?? "");
  const [portfolio, setPortfolio] = React.useState(links.portfolio ?? "");
  const [locations, setLocations] = React.useState<string[]>(initial.preferred_locations ?? []);
  const [jobTypes, setJobTypes] = React.useState<string[]>(initial.preferred_job_types ?? []);
  const [salary, setSalary] = React.useState<string>(
    typeof initial.salary_expectation?.note === "string" ? initial.salary_expectation.note : "",
  );

  const save = useMutation({
    mutationFn: () =>
      onboardingService.setCareerDetails(track, {
        links: Object.fromEntries(
          [
            ["linkedin", linkedin],
            ["github", github],
            ["portfolio", portfolio],
          ].filter(([, v]) => v.trim()),
        ),
        preferred_locations: locations,
        preferred_job_types: jobTypes,
        salary_expectation: salary.trim() ? { note: salary.trim() } : {},
      }),
    onSuccess: () => toast.success("Preferences saved"),
    onError: (err) => toastApiError(err),
  });

  const dirty =
    linkedin !== (links.linkedin ?? "") ||
    github !== (links.github ?? "") ||
    portfolio !== (links.portfolio ?? "") ||
    JSON.stringify(locations) !== JSON.stringify(initial.preferred_locations ?? []) ||
    JSON.stringify(jobTypes) !== JSON.stringify(initial.preferred_job_types ?? []) ||
    salary !==
      (typeof initial.salary_expectation?.note === "string"
        ? initial.salary_expectation.note
        : "");

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Input placeholder="LinkedIn URL" value={linkedin} onChange={(e) => setLinkedin(e.target.value)} />
        <Input placeholder="GitHub URL" value={github} onChange={(e) => setGithub(e.target.value)} />
        <Input placeholder="Portfolio URL" value={portfolio} onChange={(e) => setPortfolio(e.target.value)} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <ChipField label="Preferred locations" values={locations} onChange={setLocations} placeholder="e.g. Remote" />
        <ChipField label="Job types" values={jobTypes} onChange={setJobTypes} placeholder="e.g. Full-time" />
      </div>
      <Input
        placeholder="Salary expectation (optional)"
        value={salary}
        onChange={(e) => setSalary(e.target.value)}
      />
      <div className="flex items-center justify-end gap-3">
        {dirty && (
          <span className="text-xs text-status-interviewed">Unsaved changes</span>
        )}
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          Save preferences
        </Button>
      </div>
    </div>
  );
}
