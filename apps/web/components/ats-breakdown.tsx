"use client";

import * as React from "react";
import type { AtsBreakdown as AtsBreakdownType } from "@jd/shared-types";
import {
  Check,
  X,
  AlertTriangle,
  ShieldCheck,
  AlertCircle,
  TrendingUp,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

export function AtsScoreRing({
  score,
  size = 96,
}: {
  score: number | null;
  size?: number;
}) {
  const pct = Math.max(0, Math.min(100, score ?? 0));
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--coffee-100)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--coffee-500)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-semibold text-coffee-900">
          {score === null ? "" : Math.round(pct)}
        </span>
        <span className="text-[0.65rem] uppercase tracking-wider text-coffee-500">
          ATS
        </span>
      </div>
    </div>
  );
}

function KeywordChips({
  items,
  tone,
}: {
  items: string[];
  tone: "matched" | "missing";
}) {
  if (items.length === 0) {
    return <p className="text-sm text-coffee-400">None</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((kw) => (
        <span
          key={kw}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs",
            tone === "matched"
              ? "border-status-accepted/40 text-status-accepted"
              : "border-status-rejected/40 text-status-rejected",
          )}
        >
          {tone === "matched" ? (
            <Check className="size-3" />
          ) : (
            <X className="size-3" />
          )}
          {kw}
        </span>
      ))}
    </div>
  );
}

/**
 * The whole decision value of the ATS number is three-state: send it, fix something
 * first, or (a separate role signal) it's a reach. Derive that plain-language state
 * from the gate + must-haves + score. Handles pre-gate breakdowns gracefully (no
 * gate/criticals → falls back to the score).
 */
type Readiness = { state: "ready" | "fix"; label: string; detail: string };

function deriveReadiness(score: number | null, b: AtsBreakdownType): Readiness {
  if (b.gate?.status === "fail") {
    return {
      state: "fix",
      label: "Fix the formatting first",
      detail:
        "The document didn't pass the format check — an ATS parser may not read it correctly.",
    };
  }
  const missing = b.missing_critical ?? [];
  if (missing.length > 0) {
    return {
      state: "fix",
      label: "Add the must-haves",
      detail: `${missing.length} required skill${missing.length > 1 ? "s" : ""} not yet covered: ${missing.join(", ")}. Add where genuinely true.`,
    };
  }
  if (score !== null && score < 55) {
    return {
      state: "fix",
      label: "Strengthen coverage",
      detail:
        "Weave in more of the job's supporting keywords where they're genuinely true.",
    };
  }
  return {
    state: "ready",
    label: "Ready to send",
    detail: "Covers the job's must-haves and key supporting terms.",
  };
}

function ReadinessBanner({
  readiness,
  isReach,
}: {
  readiness: Readiness;
  isReach: boolean;
}) {
  const ready = readiness.state === "ready";
  return (
    <div className="space-y-2">
      <div
        className={cn(
          "flex items-start gap-3 rounded-lg border px-4 py-3",
          ready
            ? "border-status-offer/40 bg-status-offer/5"
            : "border-status-interviewed/40 bg-status-interviewed/5",
        )}
      >
        {ready ? (
          <ShieldCheck className="mt-0.5 size-5 shrink-0 text-status-offer" />
        ) : (
          <AlertCircle className="mt-0.5 size-5 shrink-0 text-status-interviewed" />
        )}
        <div className="min-w-0">
          <p
            className={cn(
              "text-sm font-semibold",
              ready ? "text-status-offer" : "text-status-interviewed",
            )}
          >
            {readiness.label}
          </p>
          <p className="text-sm text-coffee-600">{readiness.detail}</p>
        </div>
      </div>
      {isReach && (
        <div className="flex items-start gap-3 rounded-lg border border-coffee-300 bg-coffee-50 px-4 py-3">
          <TrendingUp className="mt-0.5 size-5 shrink-0 text-coffee-500" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-coffee-800">Reach role</p>
            <p className="text-sm text-coffee-600">
              Your title/seniority looks like a stretch for this posting — worth a
              shot, but expect tougher odds.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function MustHaves({ breakdown }: { breakdown: AtsBreakdownType }) {
  const missing = breakdown.missing_critical ?? [];
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
        Must-haves
      </p>
      <p className="flex items-center gap-2 text-sm text-coffee-700">
        {missing.length > 0 && (
          <AlertTriangle className="size-3.5 text-status-interviewed" />
        )}
        <span>
          {breakdown.criticals_covered ?? 0} of {breakdown.criticals_total} addressed
          {missing.length > 0 ? ` — missing: ${missing.join(", ")}` : ""}
        </span>
      </p>
    </div>
  );
}

function KeywordDetails({
  score,
  breakdown,
}: {
  score: number | null;
  breakdown: AtsBreakdownType;
}) {
  const [open, setOpen] = React.useState(false);
  const matched = breakdown.matched_keywords ?? [];
  const missing = breakdown.missing_keywords ?? [];
  if (matched.length === 0 && missing.length === 0) return null;
  return (
    <div className="border-t border-coffee-100 pt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-sm text-coffee-600 hover:text-coffee-900"
      >
        <span>
          Keyword breakdown
          {score !== null ? ` · ${Math.round(score)}/100 match` : ""}
        </span>
        <ChevronDown
          className={cn("size-4 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
              Matched
            </p>
            <KeywordChips items={matched} tone="matched" />
          </div>
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
              Missing
            </p>
            <KeywordChips items={missing} tone="missing" />
          </div>
        </div>
      )}
    </div>
  );
}

export function AtsBreakdown({
  score,
  breakdown,
  variant = "full",
}: {
  score: number | null;
  breakdown: AtsBreakdownType | null;
  /** "summary" = the workspace rail (readiness up top, keyword decomposition expandable
   *  in place); "full" = always-expanded decomposition. */
  variant?: "full" | "summary";
}) {
  if (!breakdown) {
    return (
      <p className="text-sm text-coffee-400">
        No breakdown available yet — generate the tailored CV to compute the ATS
        match.
      </p>
    );
  }

  const readiness = deriveReadiness(score, breakdown);
  const isReach = breakdown.stretch?.is_stretch ?? false;
  const hasCriticals =
    typeof breakdown.criticals_total === "number" && breakdown.criticals_total > 0;

  // Workspace rail: answer "should I apply?" up top, with the full keyword breakdown
  // expandable in place — no bounce-out to another page.
  if (variant === "summary") {
    return (
      <div className="flex flex-col gap-4">
        <ReadinessBanner readiness={readiness} isReach={isReach} />
        {hasCriticals && <MustHaves breakdown={breakdown} />}
        <KeywordDetails score={score} breakdown={breakdown} />
      </div>
    );
  }

  // ATS Checker: the readiness headline + the full decomposition.
  return (
    <div className="flex flex-col gap-6">
      <ReadinessBanner readiness={readiness} isReach={isReach} />
      <div className="flex items-center gap-5">
        <AtsScoreRing score={score} />
        <div className="space-y-1">
          <p className="text-sm font-medium text-coffee-900">Content readiness</p>
          <p className="max-w-prose text-sm leading-relaxed text-coffee-500">
            How well this CV covers the job&apos;s must-have and supporting keywords.
            It is not a guarantee of any employer&apos;s applicant-tracking system, and
            title/seniority fit is shown separately as a stretch signal.
          </p>
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
            Matched keywords
          </p>
          <KeywordChips items={breakdown.matched_keywords} tone="matched" />
        </div>
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
            Missing keywords
          </p>
          <KeywordChips items={breakdown.missing_keywords} tone="missing" />
        </div>
        {breakdown.ai_vetted && (
          <p className="text-xs text-coffee-500 sm:col-span-2">
            AI-vetted gap list
            {breakdown.ai_removed && breakdown.ai_removed.length > 0
              ? ` (removed: ${breakdown.ai_removed.join(", ")})`
              : ""}
          </p>
        )}
        {hasCriticals && (
          <div className="sm:col-span-2">
            <MustHaves breakdown={breakdown} />
          </div>
        )}
      </div>
    </div>
  );
}
