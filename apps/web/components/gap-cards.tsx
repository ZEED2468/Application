"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HelpCircle } from "lucide-react";
import { chatService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { toastApiError } from "@/lib/toast-error";
import { PromptCard, type PromptAnswer } from "@/components/prompt-card";

/** The CV-engine's TRUE_GAP prompts (Slice 7): a run suspended for a missing required fact raised
 *  real ChatPrompts on a linked session. Answering them all resumes the run and re-renders the CV. */
export function GapCards({
  sessionId,
  onResolved,
}: {
  sessionId: string;
  onResolved?: () => void;
}) {
  const qc = useQueryClient();
  const [answers, setAnswers] = React.useState<Record<string, PromptAnswer>>({});

  const { data } = useQuery({
    queryKey: queryKeys.chatSession(sessionId),
    queryFn: () => chatService.getSession(sessionId),
  });

  const answer = useMutation({
    mutationFn: (body: { prompt_id: string; selected: string[]; detail?: string }) =>
      chatService.answer(sessionId, body),
    onSuccess: (session) => {
      qc.setQueryData(queryKeys.chatSession(sessionId), session);
      if (session.prompts.every((p) => p.resolved)) onResolved?.();
    },
    onError: (err) => toastApiError(err),
  });

  if (!data || data.prompts.length === 0) return null;
  const open = data.prompts.filter((p) => !p.resolved).length;

  return (
    <section className="space-y-3">
      <h4 className="flex items-center gap-1.5 text-sm font-semibold text-coffee-800">
        <HelpCircle className="size-4 text-coffee-500" />
        {open > 0 ? `Answer to finish this CV · ${open}` : "All answered — re-rendering…"}
      </h4>
      {data.prompts.map((p) => {
        const value =
          answers[p.id] ?? { selected: p.selected ?? [], detail: p.detail ?? "" };
        return (
          <PromptCard
            key={p.id}
            prompt={p}
            value={value}
            confirmed={p.resolved}
            disabled={answer.isPending}
            onChange={(next) => setAnswers((a) => ({ ...a, [p.id]: next }))}
            onConfirm={() =>
              answer.mutate({
                prompt_id: p.id,
                selected: value.selected,
                detail: value.detail,
              })
            }
          />
        );
      })}
    </section>
  );
}
