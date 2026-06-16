"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles, FileText, ArrowRight } from "lucide-react";
import type {
  ChatSession,
  ChatGenerateResult,
} from "@jd/shared-types";
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

  const createSession = useMutation({
    mutationFn: (text: string) => chatService.createSession(text),
    onSuccess: (s) => {
      setSession(s);
      setAnswers({});
      setConfirmed({});
      toast.success("Session started — review the matched CV and prompts.");
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
            We never fabricate experience — these prompts only confirm what is
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
                    No CV matched yet — finish onboarding to add role CVs.
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
