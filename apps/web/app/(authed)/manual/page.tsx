"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles, FileText, ArrowRight, Plus, Pencil } from "lucide-react";
import type {
  ChatSession,
  ChatGenerateResult,
  Track,
} from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import { chatService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { TRACK_LABELS } from "@/lib/status";
import { PageHeading } from "@/components/states";
import { AtsBreakdown } from "@/components/ats-breakdown";
import { PromptCard, type PromptAnswer } from "@/components/prompt-card";
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
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

export default function ManualPage() {
  const router = useRouter();
  const [jdText, setJdText] = React.useState("");
  const [session, setSession] = React.useState<ChatSession | null>(null);
  const [answers, setAnswers] = React.useState<Record<string, PromptAnswer>>(
    {},
  );
  const [confirmed, setConfirmed] = React.useState<Record<string, boolean>>({});
  const [details, setDetails] = React.useState({
    company: "",
    role_title: "",
    track: "" as Track | "",
  });
  const [newSkill, setNewSkill] = React.useState("");

  // Sync the editable fields when a NEW session starts (same id keeps user edits).
  const sessionId = session?.session_id;
  React.useEffect(() => {
    if (session) {
      setDetails({
        company: session.company ?? "",
        role_title: session.role_title ?? "",
        track: (session.track as Track) ?? "",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const createSession = useMutation({
    mutationFn: (text: string) => chatService.createSession(text),
    onSuccess: (s) => {
      setSession(s);
      setAnswers({});
      setConfirmed({});
      toast.success("Session started, review the matched CV and prompts.");
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const updateDetails = useMutation({
    mutationFn: (_vars: { trackChanged: boolean }) =>
      chatService.update(session!.session_id, {
        company: details.company,
        role_title: details.role_title,
        track: details.track ? (details.track as Track) : undefined,
      }),
    onSuccess: (s, vars) => {
      setSession(s);
      if (vars.trackChanged) {
        // prompts changed for the new track, clear stale confirmations.
        setAnswers({});
        setConfirmed({});
      }
      toast.success(
        vars.trackChanged ? "Re-analyzed for the new track." : "Details updated.",
      );
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const addSkill = useMutation({
    mutationFn: (skill: string) =>
      chatService.addFact(session!.session_id, skill),
    onSuccess: (s) => {
      setSession(s);
      setNewSkill("");
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const answerMutation = useMutation({
    mutationFn: ({
      sessionId,
      promptId,
      answer,
    }: {
      sessionId: string;
      promptId: string;
      answer: PromptAnswer;
    }) =>
      chatService.answer(sessionId, {
        prompt_id: promptId,
        selected: answer.selected,
        detail: answer.detail || undefined,
      }),
    onSuccess: (s, vars) => {
      setSession(s);
      setConfirmed((c) => ({ ...c, [vars.promptId]: true }));
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const generate = useMutation({
    mutationFn: (sessionId: string) => chatService.generate(sessionId),
    onSuccess: (res: ChatGenerateResult) => {
      toast.success("Application created");
      router.push(`/jobs/${res.job_id}`);
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  function getAnswer(promptId: string): PromptAnswer {
    return answers[promptId] ?? { selected: [], detail: "" };
  }

  const allConfirmed =
    session?.prompts && session.prompts.length > 0
      ? session.prompts.every((p) => confirmed[p.id])
      : false;

  return (
    <div className="space-y-6">
      <PageHeading
        title="Manual Apply"
        description="Paste a job description and we'll match a CV, surface the ATS gaps, and walk through a few confirm-true questions before generating a truthful, tailored application."
      />

      {/* JD input */}
      <Card>
        <CardHeader>
          <CardTitle>Paste the job description</CardTitle>
          <CardDescription>
            We never fabricate experience, these prompts only confirm what is
            already true for you.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full job description here…"
            className="min-h-44"
          />
          <div className="flex justify-end">
            <Button
              variant="accent"
              onClick={() => createSession.mutate(jdText)}
              disabled={createSession.isPending || jdText.trim().length < 20}
            >
              <Sparkles className="size-4" />
              {createSession.isPending ? "Analyzing…" : "Analyze & start"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {session && (
        <>
          {/* Matched CV + ATS */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="size-4 text-coffee-500" />
                  Matched CV
                </CardTitle>
              </CardHeader>
              <CardContent>
                {session.matched_cv ? (
                  <div className="space-y-2">
                    <Badge variant="outline">
                      {TRACK_LABELS[session.matched_cv.track]}
                    </Badge>
                    {session.matched_cv.filename && (
                      <p className="text-sm text-coffee-700">
                        {session.matched_cv.filename}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-coffee-300">
                    No CV matched yet, add source CV files on your Profile page.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>ATS gaps</CardTitle>
              </CardHeader>
              <CardContent>
                <AtsBreakdown
                  score={session.ats?.score ?? null}
                  breakdown={session.ats?.breakdown ?? null}
                />
              </CardContent>
            </Card>
          </div>

          {/* Editable job details */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pencil className="size-4 text-coffee-500" />
                Job details
              </CardTitle>
              <CardDescription>
                Auto-filled from the JD, correct them if needed. Changing the track
                re-matches the CV and re-runs the prompts.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <Label htmlFor="company">Company</Label>
                  <Input
                    id="company"
                    value={details.company}
                    onChange={(e) =>
                      setDetails((d) => ({ ...d, company: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="role">Role title</Label>
                  <Input
                    id="role"
                    value={details.role_title}
                    onChange={(e) =>
                      setDetails((d) => ({ ...d, role_title: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="track">Track</Label>
                  <Select
                    id="track"
                    value={details.track}
                    onChange={(e) =>
                      setDetails((d) => ({ ...d, track: e.target.value as Track }))
                    }
                  >
                    {TRACKS.map((t) => (
                      <option key={t} value={t}>
                        {TRACK_LABELS[t]}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
              <div className="flex justify-end">
                <Button
                  variant="secondary"
                  disabled={updateDetails.isPending}
                  onClick={() =>
                    updateDetails.mutate({
                      trackChanged:
                        (details.track || null) !== (session.track ?? null),
                    })
                  }
                >
                  {updateDetails.isPending ? "Updating…" : "Update details"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Skills the VA knows are true */}
          <Card>
            <CardHeader>
              <CardTitle>Skills you have</CardTitle>
              <CardDescription>
                Add a real skill the JD didn&apos;t surface, truth-bounded, so only
                add what is genuinely true. These feed the tailored CV.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(session.confirmed_facts?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-2">
                  {session.confirmed_facts!.map((f) => (
                    <Badge key={f} variant="default">
                      {f}
                    </Badge>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <Input
                  placeholder="e.g. GraphQL"
                  value={newSkill}
                  onChange={(e) => setNewSkill(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && newSkill.trim()) {
                      e.preventDefault();
                      addSkill.mutate(newSkill.trim());
                    }
                  }}
                />
                <Button
                  variant="secondary"
                  disabled={addSkill.isPending || newSkill.trim().length === 0}
                  onClick={() => addSkill.mutate(newSkill.trim())}
                >
                  <Plus className="size-4" /> Add
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Prompts */}
          {session.prompts.length > 0 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-xl font-semibold text-coffee-900">
                  A few quick confirmations
                </h2>
                <p className="text-sm text-coffee-500">
                  Select what applies and add detail where it helps. Confirm each
                  one to lock it in.
                </p>
              </div>
              {session.prompts.map((prompt) => (
                <PromptCard
                  key={prompt.id}
                  prompt={prompt}
                  value={getAnswer(prompt.id)}
                  confirmed={confirmed[prompt.id]}
                  disabled={answerMutation.isPending}
                  onChange={(next) =>
                    setAnswers((a) => ({ ...a, [prompt.id]: next }))
                  }
                  onConfirm={() =>
                    answerMutation.mutate({
                      sessionId: session.session_id,
                      promptId: prompt.id,
                      answer: getAnswer(prompt.id),
                    })
                  }
                />
              ))}
            </div>
          )}

          {/* Generate */}
          <Card>
            <CardContent className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <p className="font-medium text-coffee-900">
                  Ready to generate?
                </p>
                <p className="text-sm text-coffee-500">
                  {session.prompts.length > 0 && !allConfirmed
                    ? "Confirm each prompt above first."
                    : "We'll build the tailored CV, cover letter, and application."}
                </p>
              </div>
              <Button
                variant="primary"
                onClick={() => generate.mutate(session.session_id)}
                disabled={
                  generate.isPending ||
                  (session.prompts.length > 0 && !allConfirmed)
                }
              >
                {generate.isPending ? "Generating…" : "Generate application"}
                <ArrowRight className="size-4" />
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
