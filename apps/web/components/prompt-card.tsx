"use client";

import * as React from "react";
import type { ChatPrompt } from "@jd/shared-types";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

export interface PromptAnswer {
  selected: string[];
  detail: string;
}

export function PromptCard({
  prompt,
  value,
  onChange,
  onConfirm,
  confirmed,
  disabled,
}: {
  prompt: ChatPrompt;
  value: PromptAnswer;
  onChange: (next: PromptAnswer) => void;
  onConfirm: () => void;
  confirmed?: boolean;
  disabled?: boolean;
}) {
  const multi = prompt.multi ?? true;

  function toggle(optionId: string) {
    if (disabled) return;
    let next: string[];
    if (multi) {
      next = value.selected.includes(optionId)
        ? value.selected.filter((id) => id !== optionId)
        : [...value.selected, optionId];
    } else {
      next = value.selected.includes(optionId) ? [] : [optionId];
    }
    onChange({ ...value, selected: next });
  }

  return (
    <Card
      className={cn(
        "transition-colors",
        confirmed && "border-status-accepted/50 bg-coffee-100/40",
      )}
    >
      <CardContent className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[0.7rem] uppercase tracking-wider text-coffee-500">
              {prompt.kind === "skill"
                ? "Confirm a skill"
                : prompt.kind === "reframe"
                  ? "Reframe experience"
                  : "Add detail"}
            </p>
            <p className="mt-1 text-base font-medium text-coffee-900">
              {prompt.question}
            </p>
          </div>
          {confirmed && (
            <span className="inline-flex items-center gap-1 text-xs text-status-accepted">
              <Check className="size-3.5" /> Confirmed
            </span>
          )}
        </div>

        {prompt.options.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {prompt.options.map((opt) => {
              const active = value.selected.includes(opt.id);
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => toggle(opt.id)}
                  disabled={disabled}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors disabled:opacity-60",
                    active
                      ? "border-coffee-700 bg-coffee-700 text-cream"
                      : "border-coffee-300 bg-white text-coffee-700 hover:bg-coffee-100",
                  )}
                >
                  {active && <Check className="size-3.5" />}
                  {opt.label}
                </button>
              );
            })}
          </div>
        )}

        <div className="space-y-1.5">
          <Textarea
            placeholder="Add detail (optional) — a concrete example, metric, or context that makes this true for you."
            value={value.detail}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, detail: e.target.value })}
            className="min-h-16"
          />
        </div>

        {!confirmed && (
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={onConfirm}
              disabled={disabled}
            >
              Confirm answer
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
