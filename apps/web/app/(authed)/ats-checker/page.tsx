"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, ScanSearch, UploadCloud, Sparkles } from "lucide-react";
import type { AtsCheckResult, Track } from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import { atsService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { previewCoverLetterTemplate } from "@/lib/cover-letter-template";
import { PageHeading } from "@/components/states";
import { AtsBreakdown } from "@/components/ats-breakdown";
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
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";

const CV_ACCEPT =
  ".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export default function AtsCheckerPage() {
  const [jdText, setJdText] = React.useState("");
  const [cvText, setCvText] = React.useState("");
  const [roleTitle, setRoleTitle] = React.useState("");
  const [cvFile, setCvFile] = React.useState<File | null>(null);
  const [useAi, setUseAi] = React.useState(true);
  const [result, setResult] = React.useState<AtsCheckResult | null>(null);
  const [selectedTrack, setSelectedTrack] = React.useState<Track | "">("");
  const [trackManual, setTrackManual] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const sourcesQuery = useQuery({
    queryKey: queryKeys.atsSources,
    queryFn: () => atsService.sources(),
  });

  const profileTracks = sourcesQuery.data?.tracks ?? [];
  const profileByTrack = React.useMemo(() => {
    const map = new Map<Track, (typeof profileTracks)[number]>();
    profileTracks.forEach((t) => map.set(t.track, t));
    return map;
  }, [profileTracks]);

  const hasProfileCvs = profileTracks.length > 0;
  const activeProfile =
    selectedTrack && profileByTrack.has(selectedTrack)
      ? profileByTrack.get(selectedTrack)!
      : null;
  const useProfileCv = Boolean(activeProfile) && !cvFile && cvText.trim().length < 20;

  const coverLetterTemplate =
    result?.cover_letter_template ?? sourcesQuery.data?.cover_letter_template ?? null;

  const coverLetterPreview = React.useMemo(
    () => previewCoverLetterTemplate(coverLetterTemplate?.body ?? ""),
    [coverLetterTemplate?.body],
  );

  React.useEffect(() => {
    if (!hasProfileCvs || trackManual || selectedTrack) return;
    const first = profileTracks[0]?.track;
    if (first) setSelectedTrack(first);
  }, [hasProfileCvs, profileTracks, selectedTrack, trackManual]);

  React.useEffect(() => {
    if (!hasProfileCvs || trackManual) return;
    const jd = jdText.trim();
    if (jd.length < 20) return;

    const timer = window.setTimeout(() => {
      atsService
        .suggestTrack({ jdText: jd, roleTitle: roleTitle || undefined })
        .then((match) => {
          if (profileByTrack.has(match.track)) {
            setSelectedTrack(match.track);
          }
        })
        .catch(() => {});
    }, 600);

    return () => window.clearTimeout(timer);
  }, [jdText, roleTitle, hasProfileCvs, trackManual, profileByTrack]);

  const check = useMutation({
    mutationFn: () =>
      atsService.check({
        jdText,
        track: useProfileCv ? (selectedTrack as Track) : undefined,
        cvText: useProfileCv ? undefined : cvText,
        cvFile: useProfileCv ? undefined : cvFile,
        roleTitle: roleTitle || undefined,
        useAi,
      }),
    onSuccess: (data) => {
      setResult(data);
      if (data.track && !trackManual) {
        setSelectedTrack(data.track);
      }
      toast.success("ATS check complete");
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const canRun =
    jdText.trim().length >= 20 &&
    (useProfileCv || cvFile !== null || cvText.trim().length >= 20);

  return (
    <div className="space-y-6">
      <PageHeading
        title="ATS Checker"
        description="Vet any CV against any job description. Uses your profile CV when uploaded, otherwise paste or upload. Rule-based keyword match first, then optional AI review."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Job description</CardTitle>
            <CardDescription>Paste the full JD you are applying to.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="role-title">Role title (optional)</Label>
              <Input
                id="role-title"
                placeholder="e.g. Backend Engineer"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
              />
            </div>
            <Textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste job description…"
              className="min-h-52"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>CV / resume</CardTitle>
            <CardDescription>
              {hasProfileCvs
                ? "Pick a profile track or paste/upload when none is on file."
                : "Upload a file or paste plain text."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {hasProfileCvs && (
              <div className="space-y-1.5">
                <Label htmlFor="cv-track">Profile CV track</Label>
                <Select
                  id="cv-track"
                  value={selectedTrack}
                  onChange={(e) => {
                    setTrackManual(true);
                    setSelectedTrack(e.target.value as Track);
                    setCvFile(null);
                    setCvText("");
                  }}
                >
                  <option value="">Select track…</option>
                  {TRACKS.filter((t) => profileByTrack.has(t)).map((t) => (
                    <option key={t} value={t}>
                      {TRACK_LABELS[t]}
                      {profileByTrack.get(t)?.filename
                        ? ` · ${profileByTrack.get(t)!.filename}`
                        : ""}
                    </option>
                  ))}
                </Select>
              </div>
            )}

            {useProfileCv && activeProfile ? (
              <div className="rounded-md border border-coffee-300 bg-coffee-50 px-4 py-3 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <FileText className="size-4 text-coffee-500" />
                  <Badge variant="outline">{TRACK_LABELS[activeProfile.track]}</Badge>
                  {activeProfile.filename && (
                    <span className="text-sm text-coffee-700">{activeProfile.filename}</span>
                  )}
                </div>
                <p className="text-xs text-coffee-500">
                  Using profile CV · {activeProfile.word_count.toLocaleString()} words
                  {activeProfile.confirmed ? " · confirmed" : ""}
                </p>
              </div>
            ) : (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept={CV_ACCEPT}
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null;
                    setCvFile(f);
                    if (f) setCvText("");
                    e.target.value = "";
                  }}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => fileRef.current?.click()}
                  >
                    <UploadCloud className="size-4" />
                    {cvFile ? cvFile.name : "Upload PDF/DOCX"}
                  </Button>
                  {cvFile && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setCvFile(null)}
                    >
                      Clear file
                    </Button>
                  )}
                </div>
                <Textarea
                  value={cvText}
                  onChange={(e) => {
                    setCvText(e.target.value);
                    if (e.target.value.trim()) setCvFile(null);
                  }}
                  placeholder="Or paste CV text…"
                  className="min-h-52"
                  disabled={Boolean(cvFile)}
                />
                {hasProfileCvs && !selectedTrack && (
                  <p className="text-xs text-coffee-500">
                    Select a profile track above, or paste/upload a one-off CV here.
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {coverLetterTemplate?.body && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Cover letter template
              <Badge variant="muted">Auto-selected</Badge>
            </CardTitle>
            <CardDescription>
              {coverLetterTemplate.filename
                ? coverLetterTemplate.filename
                : "From your Profile page"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-coffee-300 bg-coffee-50 p-3 text-sm text-coffee-700">
              {coverLetterPreview || coverLetterTemplate.body}
            </pre>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="flex flex-col gap-4 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-coffee-700">
            <input
              type="checkbox"
              checked={useAi}
              onChange={(e) => setUseAi(e.target.checked)}
              className="size-4 rounded border-coffee-300"
            />
            Include AI analysis (requires LLM on API)
          </label>
          <Button
            variant="accent"
            disabled={!canRun || check.isPending}
            onClick={() => check.mutate()}
          >
            <ScanSearch className="size-4" />
            {check.isPending ? "Checking…" : "Run ATS check"}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{result.role_title}</Badge>
            {result.track && (
              <Badge variant="outline">{TRACK_LABELS[result.track]}</Badge>
            )}
            {result.cv_source === "profile" && (
              <Badge variant="muted">Profile CV</Badge>
            )}
            {result.cv_filename && (
              <Badge variant="muted">{result.cv_filename}</Badge>
            )}
            <span className="text-sm text-coffee-500">
              {result.cv_word_count.toLocaleString()} words in CV
            </span>
          </div>

          {result.track_match?.reason && (
            <p className="text-sm text-coffee-600">
              {result.track_match.method === "ai" ? "AI track pick: " : "Track match: "}
              {result.track_match.reason}
            </p>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Keyword match</CardTitle>
                <CardDescription>
                  Fast rule-based scan (same engine as Manual Apply).
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AtsBreakdown
                  score={result.rule_based.score}
                  breakdown={result.rule_based.breakdown}
                />
                {result.rule_based.gaps.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
                      Rule-based gaps
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {result.rule_based.gaps.map((g) => (
                        <Badge key={g} variant="outline">
                          {g}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {result.ai && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="size-4 text-coffee-500" />
                    AI review
                    {result.ai.ai_powered === false && (
                      <Badge variant="muted">Offline</Badge>
                    )}
                  </CardTitle>
                  <CardDescription>
                    {result.ai.fit_summary || "No summary returned."}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="flex items-center gap-4">
                    <div className="text-3xl font-semibold text-coffee-900">
                      {result.ai.fit_score != null
                        ? Math.round(result.ai.fit_score)
                        : "—"}
                    </div>
                    <div>
                      <p className="font-medium text-coffee-900">
                        {result.ai.verdict || "Fit assessment"}
                      </p>
                      <p className="text-xs text-coffee-500">AI fit score</p>
                    </div>
                  </div>

                  {result.ai.strengths.length > 0 && (
                    <Section title="Strengths" items={result.ai.strengths} />
                  )}

                  {result.ai.gaps.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
                        Real gaps
                      </p>
                      <ul className="space-y-2">
                        {result.ai.gaps.map((g) => (
                          <li
                            key={g.skill}
                            className="rounded-md border border-coffee-300 px-3 py-2 text-sm"
                          >
                            <span className="font-medium text-coffee-900">
                              {g.skill}
                            </span>
                            <Badge variant="outline" className="ml-2 text-[0.65rem]">
                              {g.severity}
                            </Badge>
                            {g.reason && (
                              <p className="mt-1 text-coffee-600">{g.reason}</p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {result.ai.false_positives.length > 0 && (
                    <Section
                      title="Not real gaps"
                      items={result.ai.false_positives}
                    />
                  )}

                  {result.ai.recommendations.length > 0 && (
                    <Section
                      title="Recommendations"
                      items={result.ai.recommendations}
                    />
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
        {title}
      </p>
      <ul className="list-inside list-disc space-y-1 text-sm text-coffee-700">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
