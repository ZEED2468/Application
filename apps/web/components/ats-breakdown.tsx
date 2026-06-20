import type { AtsBreakdown as AtsBreakdownType } from "@jd/shared-types";
import { Check, X, AlertTriangle } from "lucide-react";
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
    return <p className="text-sm text-coffee-300">None</p>;
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

export function AtsBreakdown({
  score,
  breakdown,
}: {
  score: number | null;
  breakdown: AtsBreakdownType | null;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-5">
        <AtsScoreRing score={score} />
        <div className="space-y-1">
          <p className="text-sm font-medium text-coffee-900">
            Internal ATS match
          </p>
          <p className="max-w-prose text-sm leading-relaxed text-coffee-500">
            This is our internal ATS match, optimized toward a 90–95% target. It
            estimates how well the tailored CV aligns with this job&apos;s
            keywords and formatting, it is not a guarantee of any employer&apos;s
            applicant-tracking system.
          </p>
        </div>
      </div>

      {breakdown ? (
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
          {breakdown.format_flags.length > 0 && (
            <div className="space-y-2 sm:col-span-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
                Format flags
              </p>
              <ul className="space-y-1">
                {breakdown.format_flags.map((flag) => (
                  <li
                    key={flag}
                    className="flex items-center gap-2 text-sm text-coffee-700"
                  >
                    <AlertTriangle className="size-3.5 text-status-interviewed" />
                    {flag}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-coffee-300">
          No breakdown available yet, generate the tailored CV to compute the
          ATS match.
        </p>
      )}
    </div>
  );
}
