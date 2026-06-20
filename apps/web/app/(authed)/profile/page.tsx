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
    onSuccess: (_data, vars) => {
      toast.success(`Source CV saved for ${TRACK_LABELS[vars.track]}`);
      queryClient.invalidateQueries({ queryKey: queryKeys.profiles });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const templateMutation = useMutation({
    mutationFn: (body: string) =>
      onboardingService.setCoverLetterTemplate(body),
    onSuccess: () => toast.success("Cover-letter template saved"),
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
        description="Upload your source CV file once per track. The engine generates a new tailored CV and cover letter (PDF) for each job — your uploads are never overwritten."
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
                      ? "border-coffee-700 bg-coffee-700 text-cream"
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
            Upload a PDF or Word file — this is your master CV for the track. We
            parse it into a structured profile (nothing fabricated). Per-job
            applications get a newly generated, tailored PDF in the tracker.
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
                    <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-coffee-300 px-3 py-1.5 text-sm text-coffee-700 transition-colors hover:bg-coffee-100">
                      <UploadCloud className="size-4" />
                      {profile?.role_cv ? "Replace file" : "Upload file"}
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) uploadMutation.mutate({ track, file });
                          e.target.value = "";
                        }}
                      />
                    </label>
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
            A base template for generated cover letters. Use placeholders like
            {" {company} "} and {" {role} "}. Each application gets its own PDF.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="cover">Template body</Label>
            <Textarea
              id="cover"
              value={coverLetter}
              onChange={(e) => setCoverLetter(e.target.value)}
              placeholder="Dear {company} team, I'm excited about the {role} role…"
              className="min-h-40"
            />
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
