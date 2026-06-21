"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UploadCloud, Check, FileText, Lock } from "lucide-react";
import type { MasterProfile, MeResponse, Track } from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import { authService, onboardingService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { previewCoverLetterTemplate } from "@/lib/cover-letter-template";
import { PageHeading, EmptyState } from "@/components/states";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const [selectedTracks, setSelectedTracks] = React.useState<Track[]>([]);
  const [coverLetter, setCoverLetter] = React.useState("");
  const [templateFilename, setTemplateFilename] = React.useState<string | null>(
    null,
  );
  const [templateLoaded, setTemplateLoaded] = React.useState(false);
  const [uploadingTrack, setUploadingTrack] = React.useState<Track | null>(null);

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

  function toggleTrack(track: Track) {
    setSelectedTracks((cur) =>
      cur.includes(track) ? cur.filter((t) => t !== track) : [...cur, track],
    );
  }

  const uploadMutation = useMutation({
    mutationFn: ({ track, file }: { track: Track; file: File }) =>
      onboardingService.uploadRoleCv(track, file),
    onMutate: ({ track }) => setUploadingTrack(track),
    onSuccess: (_data, vars) => {
      const structured = _data as {
        structured_by?: string;
        experience_entries?: number;
      };
      const detail =
        structured.structured_by === "llm"
          ? `Structured with AI (${structured.experience_entries ?? 0} experience blocks). Review and confirm.`
          : profileByTrack.get(vars.track)?.role_cv
            ? `${TRACK_LABELS[vars.track]} CV replaced, review and confirm again`
            : `${TRACK_LABELS[vars.track]} source CV saved`;
      toast.success(detail);
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
    onSettled: () => setUploadingTrack(null),
  });

  const templateUploadMutation = useMutation({
    mutationFn: (file: File) => onboardingService.uploadCoverLetterTemplate(file),
    onSuccess: (data) => {
      toast.success("Cover-letter file uploaded, text loaded into template");
      setCoverLetter(data.body ?? "");
      setTemplateFilename(data.filename ?? null);
      setTemplateLoaded(true);
      queryClient.invalidateQueries({ queryKey: queryKeys.coverLetterTemplate });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const templateMutation = useMutation({
    mutationFn: (body: string) =>
      onboardingService.setCoverLetterTemplate(body),
    onSuccess: (data) => {
      toast.success("Cover-letter template saved");
      setTemplateFilename(data.filename ?? null);
      queryClient.invalidateQueries({ queryKey: queryKeys.coverLetterTemplate });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const confirmMutation = useMutation({
    mutationFn: (track: Track) => onboardingService.confirm(track),
    onSuccess: (_d, track) => {
      toast.success(`${TRACK_LABELS[track]} profile confirmed`);
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  if (me?.type === "va") {
    return (
      <EmptyState
        icon={<Lock className="size-8" />}
        title="Profile is hunter-only"
        description="Source CVs and cover-letter templates are managed by the hunter you assist."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeading
        title="Profile"
        description="Upload your source CV once per track. Replace it anytime, per-job applications still get newly tailored PDFs."
      />

      <Card>
        <CardHeader>
          <CardTitle>1 · Select your tracks</CardTitle>
          <CardDescription>
            Pick every track you hunt across. Each track gets its own source CV
            file.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {TRACKS.map((track) => {
              const active = selectedTracks.includes(track);
              const confirmed = profileByTrack.get(track)?.confirmed;
              return (
                <button
                  key={track}
                  type="button"
                  onClick={() => toggleTrack(track)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm transition-colors",
                    active
                      ? "border-coffee-700 bg-coffee-700 text-white"
                      : "border-coffee-300 bg-white text-coffee-700 hover:bg-coffee-100",
                  )}
                >
                  {(active || confirmed) && <Check className="size-3.5" />}
                  {TRACK_LABELS[track]}
                  {confirmed && (
                    <span className="text-xs opacity-80">· confirmed</span>
                  )}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2 · Source CV file (one per track)</CardTitle>
          <CardDescription>
            Upload a PDF or Word file — we extract text and structure skills and
            experience (AI when configured on the API). Replace anytime; confirm
            again after re-upload.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {profilesQuery.isLoading && <Skeleton className="h-20 w-full" />}
          {(selectedTracks.length === 0
            ? Array.from(profileByTrack.keys())
            : selectedTracks
          ).length === 0 && !profilesQuery.isLoading ? (
            <p className="text-sm text-coffee-300">
              Select at least one track above to upload a source CV file.
            </p>
          ) : (
            (selectedTracks.length === 0
              ? Array.from(profileByTrack.keys())
              : selectedTracks
            ).map((track) => {
              const profile = profileByTrack.get(track);
              return (
                <div
                  key={track}
                  className="flex flex-col gap-3 rounded-md border border-coffee-100 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <Badge variant="outline">{TRACK_LABELS[track]}</Badge>
                    {profile?.role_cv?.filename ? (
                      <span className="flex min-w-0 items-center gap-1.5 text-sm text-coffee-700">
                        <FileText className="size-4 shrink-0 text-coffee-500" />
                        <span className="truncate" title={profile.role_cv.filename}>
                          {profile.role_cv.filename}
                        </span>
                        {profile.role_cv.parsed && (
                          <span className="shrink-0 text-xs text-status-offer">
                            parsed
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-sm text-coffee-300">
                        No source file uploaded
                      </span>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <CvUploadButton
                      track={track}
                      hasFile={Boolean(profile?.role_cv)}
                      isUploading={
                        uploadMutation.isPending && uploadingTrack === track
                      }
                      onFile={(file) => uploadMutation.mutate({ track, file })}
                    />
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={
                        confirmMutation.isPending ||
                        profile?.confirmed ||
                        !profile?.role_cv?.parsed
                      }
                      onClick={() => confirmMutation.mutate(track)}
                    >
                      {profile?.confirmed ? "Confirmed" : "Confirm profile"}
                    </Button>
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3 · Cover-letter template</CardTitle>
          <CardDescription>
            Upload a Word or PDF file, or write a template directly. Use
            placeholders like {" {company} "}, {" {role} "}, and {" {name} "}.
            The preview shows how it will read for a sample job, each
            application still gets its own tailored PDF.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex flex-col gap-3 rounded-md border border-coffee-100 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              {templateFilename ? (
                <span className="flex min-w-0 items-center gap-1.5 text-sm text-coffee-700">
                  <FileText className="size-4 shrink-0 text-coffee-500" />
                  <span className="truncate" title={templateFilename}>
                    {templateFilename}
                  </span>
                </span>
              ) : (
                <span className="text-sm text-coffee-300">
                  No template file uploaded
                </span>
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
              <p className="text-xs text-coffee-400">
                Edit freely after upload, this text is what the engine uses when
                tailoring cover letters.
              </p>
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
                    Your template preview will appear here as you type or upload
                    a file.
                  </p>
                )}
              </div>
              <p className="text-xs text-coffee-400">
                Sample values: Acme Corp · Senior Engineer · your first name.
              </p>
            </div>
          </div>

          <div className="flex justify-end">
            <Button
              variant="secondary"
              disabled={
                templateMutation.isPending || coverLetter.trim().length === 0
              }
              onClick={() => templateMutation.mutate(coverLetter)}
            >
              Save template
            </Button>
          </div>
        </CardContent>
      </Card>
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
        variant="secondary"
        disabled={isUploading}
        onClick={() => inputRef.current?.click()}
      >
        <UploadCloud className="size-4" />
        {isUploading
          ? "Uploading…"
          : hasFile
            ? "Replace file"
            : "Upload file"}
      </Button>
    </>
  );
}
