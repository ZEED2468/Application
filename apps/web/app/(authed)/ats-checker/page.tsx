"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight, ScanSearch, Sparkles } from "lucide-react";
import type { Track } from "@jd/shared-types";
import { atsService, jobsService } from "@/lib/api/services";
import { toastApiError } from "@/lib/toast-error";
import { TRACK_LABELS } from "@/lib/status";
import { PageHeading } from "@/components/states";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";

export const dynamic = "force-dynamic";

/**
 * The "Tailor" nav door. Paste a JD, pick a track, and open the SAME job workspace a
 * discovered job opens (generate → review → apply). No analysis-then-handoff: the JD
 * becomes a manual job and we route to /jobs/{id}.
 */
export default function TailorPage() {
  const router = useRouter();
  const [jdText, setJdText] = React.useState("");
  const [roleTitle, setRoleTitle] = React.useState("");
  const [track, setTrack] = React.useState<Track | "">("");
  const [trackTouched, setTrackTouched] = React.useState(false);

  // Older links arrive as /ats-checker?job_id=… — the workspace is canonical now, so
  // send them straight there.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const jid = new URLSearchParams(window.location.search).get("job_id");
    if (jid) router.replace(`/jobs/${jid}`);
  }, [router]);

  const { data: sources } = useQuery({
    queryKey: ["ats", "sources"],
    queryFn: () => atsService.sources(),
    staleTime: 5 * 60 * 1000,
  });
  const trackOptions = sources?.tracks ?? [];

  // Auto-suggest the best track from the JD (debounced) until the user picks one.
  React.useEffect(() => {
    const jd = jdText.trim();
    if (trackTouched || jd.length < 40) return;
    const t = window.setTimeout(async () => {
      try {
        const s = await atsService.suggestTrack({
          jdText: jd,
          roleTitle: roleTitle || undefined,
        });
        setTrack((prev) => (trackTouched ? prev : s.track));
      } catch {
        /* non-fatal: the user can pick a track, or auto-detect on the server */
      }
    }, 700);
    return () => window.clearTimeout(t);
  }, [jdText, roleTitle, trackTouched]);

  const open = useMutation({
    mutationFn: () =>
      jobsService.createFromJd({
        jd_text: jdText.trim(),
        role_title: roleTitle.trim() || undefined,
        track: track || undefined,
      }),
    onSuccess: (res) => router.push(`/jobs/${res.job_id}`),
    onError: (err) => toastApiError(err, "Couldn't open the tailor workspace"),
  });

  const canOpen = jdText.trim().length > 0 && !open.isPending;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <PageHeading
        title="Tailor"
        description="Paste a job description to tailor your résumé for it. It opens as a workspace where you generate, review, and apply — the same place a job from your list opens."
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ScanSearch className="size-5" /> Tailor for a job description
          </CardTitle>
          <CardDescription>
            The tailored CV is built from your profile for the chosen track —
            truth-bounded, no invented facts.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="jd">Job description</Label>
            <Textarea
              id="jd"
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste the full job description here…"
              className="min-h-[220px] text-sm"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canOpen) {
                  open.mutate();
                }
              }}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="role">Role title (optional)</Label>
              <Input
                id="role"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                placeholder="e.g. Backend Engineer"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="track">Track</Label>
              <Select
                id="track"
                value={track}
                onChange={(e) => {
                  setTrack(e.target.value as Track | "");
                  setTrackTouched(true);
                }}
              >
                <option value="">Auto-detect from JD</option>
                {trackOptions.map((t) => (
                  <option key={t.track} value={t.track}>
                    {TRACK_LABELS[t.track] ?? t.track}
                    {t.confirmed ? "" : " (unconfirmed)"}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {sources && trackOptions.length === 0 && (
            <p className="text-sm text-coffee-500">
              You don&apos;t have a source CV yet.{" "}
              <Link href="/profile" className="underline underline-offset-2">
                Upload one on your Profile
              </Link>{" "}
              so the tailored CV has real facts to work from.
            </p>
          )}

          <div className="flex justify-end">
            <Button
              variant="primary"
              onClick={() => open.mutate()}
              disabled={!canOpen}
            >
              <Sparkles className="size-4" />
              {open.isPending ? "Opening…" : "Open in workspace"}
              {!open.isPending && <ArrowRight className="size-4" />}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
