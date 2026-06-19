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

export default function OnboardingPage() {
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
      toast.success(`CV uploaded for ${TRACK_LABELS[vars.track]}`);
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

  // Editing source content (CV / cover letter / profile) is hunter-only. VAs assist
  // elsewhere; the backend also 403s these endpoints. (Nav hides this for VAs.)
  if (me?.type === "va") {
    return (
      <EmptyState
        icon={<Lock className="size-8" />}
        title="Onboarding is hunter-only"
        description="Your CV and cover-letter content are managed by the hunter you assist."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeading
        title="Onboarding"
        description="Choose your tracks, upload one CV per track, set a cover-letter template, then review and confirm the parsed profile."
      />

      {/* Step 1: tracks */}
      <Card>
        <CardHeader>
          <CardTitle>1 · Select your tracks</CardTitle>
          <CardDescription>
            Pick every track you want to hunt across. You can confirm them
            independently below.
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

      {/* Step 2: per-track CV upload + confirm */}
      <Card>
        <CardHeader>
          <CardTitle>2 · Upload a CV per track</CardTitle>
          <CardDescription>
            We parse each CV into a structured profile. Nothing is fabricated —
            you review before confirming.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {profilesQuery.isLoading && (
            <Skeleton className="h-20 w-full" />
          )}
          {(selectedTracks.length === 0
            ? Array.from(profileByTrack.keys())
            : selectedTracks
          ).length === 0 && !profilesQuery.isLoading ? (
            <p className="text-sm text-coffee-300">
              Select at least one track above to upload a CV.
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
                  <div className="flex items-center gap-3">
                    <Badge variant="outline">{TRACK_LABELS[track]}</Badge>
                    {profile?.role_cv ? (
                      <span className="flex items-center gap-1.5 text-sm text-coffee-700">
                        <FileText className="size-4 text-coffee-500" />
                        {profile.role_cv.filename}
                        {profile.role_cv.parsed && (
                          <span className="text-xs text-status-accepted">
                            parsed
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-sm text-coffee-300">
                        No CV uploaded
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-coffee-300 px-3 py-1.5 text-sm text-coffee-700 transition-colors hover:bg-coffee-100">
                      <UploadCloud className="size-4" />
                      Upload CV
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file)
                            uploadMutation.mutate({ track, file });
                          e.target.value = "";
                        }}
                      />
                    </label>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={
                        confirmMutation.isPending || profile?.confirmed
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

      {/* Step 3: cover letter template */}
      <Card>
        <CardHeader>
          <CardTitle>3 · Cover-letter template</CardTitle>
          <CardDescription>
            A base template tailored per application. Use placeholders like
            {" {company} "} and {" {role} "}.
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
