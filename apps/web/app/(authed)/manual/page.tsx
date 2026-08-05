"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Sparkles,
  FileText,
  ArrowRight,
  ArrowLeft,
  Plus,
  Pencil,
  Wand2,
} from "lucide-react";
import type {
  ChatSession,
  ChatGenerateResult,
  Track,
} from "@jd/shared-types";
import { TRACKS } from "@jd/shared-types";
import { chatService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
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

/** Rebuild the local answer/confirmation maps from a session the server sent back,
 *  so a reload restores exactly what the user had already confirmed. */
function hydrateAnswers(s: ChatSession): {
  answers: Record<string, PromptAnswer>;
  confirmed: Record<string, boolean>;
} {
  const answers: Record<string, PromptAnswer> = {};
  const confirmed: Record<string, boolean> = {};
  s.prompts.forEach((p) => {
    if (p.selected?.length || p.detail) {
      answers[p.id] = { selected: p.selected ?? [], detail: p.detail ?? "" };
    }
    if (p.resolved) confirmed[p.id] = true;
  });
  return { answers, confirmed };
}

export default function ManualPage() {
  const router = useRouter();
  const [jdText, setJdText] = React.useState("");
  const [session, setSession] = React.useState<ChatSession | null>(null);
  const [answers, setAnswers] = React.useState<Record<string, PromptAnswer>>(
    {},
  );
  const [confirmed, setConfirmed] = React.useState<Record<string, boolean>>({});
  // Read synchronously so the restore has no first-render race with the handoff.
  const [resumeId] = React.useState<string | null>(() =>
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("session")
      : null,
  );
  const [details, setDetails] = React.useState({
    company: "",
    role_title: "",
    track: "" as Track | "",
  });
  const [newSkill, setNewSkill] = React.useState("");
  const [jdOpen, setJdOpen] = React.useState(false);

  const [aiVetted, setAiVetted] = React.useState(false);

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
      setAiVetted(false);
      // The session id lives in the URL from here on: the server already persists the
      // JD, the matched CV, the ATS breakdown and every confirmation, so a reload,
      // a back-navigation or a shared link resumes the work instead of discarding it.
      router.replace(`/manual?session=${s.session_id}`, { scroll: false });
      toast.success("Session started, review the matched CV and prompts.");
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  // Resuming ?session=… — pull the whole session back and rehydrate the answers.
  const resumeQuery = useQuery({
    queryKey: queryKeys.chatSession(resumeId ?? ""),
    queryFn: () => chatService.getSession(resumeId!),
    enabled: Boolean(resumeId),
    retry: false,
  });

  const resumed = React.useRef(false);
  React.useEffect(() => {
    if (resumed.current || !resumeQuery.data) return;
    resumed.current = true;
    const s = resumeQuery.data;
    setSession(s);
    setJdText(s.jd_text ?? "");
    const { answers: a, confirmed: c } = hydrateAnswers(s);
    setAnswers(a);
    setConfirmed(c);
    setAiVetted(Boolean(s.ats?.breakdown?.ai_vetted));
  }, [resumeQuery.data]);

  React.useEffect(() => {
    if (resumeQuery.isError) {
      toast.error("That session is no longer available — start a new one below.");
    }
  }, [resumeQuery.isError]);

  // Arriving from Tailor's "Create application": start the session from the handed-off
  // JD so it isn't re-pasted or re-analyzed.
  const autoStarted = React.useRef(false);
  React.useEffect(() => {
    if (autoStarted.current || resumeId) return;
    let jd = "";
    try {
      const raw = window.sessionStorage.getItem("tailor-apply-handoff");
      if (raw) {
        window.sessionStorage.removeItem("tailor-apply-handoff");
        jd = (JSON.parse(raw) as { jd_text?: string }).jd_text ?? "";
      }
    } catch {
      jd = "";
    }
    if (jd.trim().length >= 20) {
      autoStarted.current = true;
      setJdText(jd);
      createSession.mutate(jd);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const vetGaps = useMutation({
    mutationFn: () => chatService.vetGaps(session!.session_id),
    onSuccess: (s) => {
      setSession(s);
      setAnswers({});
      setConfirmed({});
      setAiVetted(Boolean(s.ats?.breakdown?.ai_vetted));
      const removed = s.ats?.breakdown?.ai_removed?.length ?? 0;
      toast.success(
        removed > 0
          ? `AI vet complete. ${removed} noise gap(s) removed, prompts updated.`
          : "AI vet complete. Prompts updated.",
      );
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const generate = useMutation({
    mutationFn: (sessionId: string) => chatService.generate(sessionId),
    onSuccess: (res: ChatGenerateResult) => {
      toast.success("Tailored CV ready — review it, then apply.");
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

  /** Drop the current session and return to a blank JD box. */
  function startOver() {
    setSession(null);
    setAnswers({});
    setConfirmed({});
    setAiVetted(false);
    setJdText("");
    setJdOpen(false);
    router.replace("/manual", { scroll: false });
  }

  return (
    <div className="space-y-6">
      <Link
        href="/ats-checker"
        className="inline-flex items-center gap-1.5 text-sm text-coffee-500 hover:text-coffee-700"
      >
        <ArrowLeft className="size-4" />
        Back to Tailor
      </Link>
      <PageHeading
        title="Create application"
        description="Confirm a few true details, then generate a tailored CV, cover letter, and a tracked application. Paste a JD to start, or continue from a Tailor analysis."
      />

      {resumeQuery.isLoading && (
        <p className="rounded-md border border-coffee-200 bg-coffee-50 px-4 py-3 text-sm text-coffee-600">
          Picking up where you left off…
        </p>
      )}

      {/* JD input — once a session exists the JD is settled context, not an invitation
          to start a second one. Collapsed by default with an explicit way back out. */}
      {session ? (
        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
            <div className="min-w-0">
              <CardTitle>Job description</CardTitle>
              <CardDescription>
                Analyzed for this application. Starting over discards the
                confirmations below.
              </CardDescription>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setJdOpen((o) => !o)}
              >
                {jdOpen ? "Hide" : "Show"}
              </Button>
              <Button variant="secondary" size="sm" onClick={startOver}>
                Start over
              </Button>
            </div>
          </CardHeader>
          {jdOpen && (
            <CardContent>
              <p className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-coffee-200 bg-coffee-50 px-3 py-2 text-sm leading-relaxed text-coffee-700">
                {jdText || "No job description on file."}
              </p>
            </CardContent>
          )}
        </Card>
      ) : (
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
      )}

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
                    {session.track_match?.reason && (
                      <p className="text-xs text-coffee-500">
                        {session.track_match.method === "ai" ? "AI: " : ""}
                        {session.track_match.reason}
                      </p>
                    )}
                    {session.matched_cv.filename && (
                      <p className="text-sm text-coffee-700">
                        {session.matched_cv.filename}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-coffee-400">
                    No CV matched yet, add source CV files on your Profile page.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
                <CardTitle>ATS gaps</CardTitle>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={vetGaps.isPending}
                  onClick={() => vetGaps.mutate()}
                >
                  <Wand2 className="size-4" />
                  {vetGaps.isPending ? "Vetting…" : "Vet with AI"}
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {aiVetted || session.ats?.breakdown?.ai_vetted ? (
                  <p className="text-xs text-coffee-500">
                    Gaps reviewed with AI. Confirm prompts below reflect real
                    missing skills only.
                    {session.ats?.breakdown?.ai_notes
                      ? ` ${session.ats.breakdown.ai_notes}`
                      : ""}
                  </p>
                ) : (
                  <p className="text-xs text-coffee-500">
                    Rule-based scan complete. Use &quot;Vet with AI&quot; to filter
                    noise and refine confirm prompts (requires LLM configured on
                    the API).
                  </p>
                )}
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
                Auto-filled from the JD. Track picks the best uploaded CV (AI when
                configured). Change it if needed — changing track re-matches and
                re-runs prompts.
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
