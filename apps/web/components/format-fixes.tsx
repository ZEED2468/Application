import {
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  Wand2,
} from "lucide-react";
import type { CvRunResult, CvViolation } from "@jd/shared-types";
import { AtsScoreRing } from "./ats-breakdown";

const RULE_LABEL: Record<string, string> = {
  "structure.date_format": "Date format",
  "structure.clean_text": "Spacing & bullets",
};

function ruleLabel(id: string): string {
  return RULE_LABEL[id] ?? id.replace(/^[a-z]+\./, "").replace(/_/g, " ");
}

const SEVERITY_ORDER: Record<CvViolation["severity"], number> = {
  critical: 0,
  major: 1,
  minor: 2,
};

/** The deterministic "we fixed your CV's format" report: score on the compiled artifact,
 *  what got fixed (before→after), and any remaining issues. */
export function FormatFixes({ run }: { run: CvRunResult }) {
  const { delta, state, score, violations } = run;
  const released = state === "released";
  const measured = score !== null;
  const remaining = [...violations].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );

  return (
    <div className="space-y-6">
      {/* Outcome header */}
      <div
        className={
          released
            ? "flex items-center gap-4 rounded-lg border border-green-200 bg-green-50 p-4"
            : "flex items-center gap-4 rounded-lg border border-amber-200 bg-amber-50 p-4"
        }
      >
        <AtsScoreRing score={score} size={64} />
        <div className="min-w-0">
          <p
            className={
              released
                ? "flex items-center gap-1.5 font-semibold text-green-800"
                : "flex items-center gap-1.5 font-semibold text-amber-800"
            }
          >
            {released ? (
              <ShieldCheck className="size-4" />
            ) : (
              <AlertTriangle className="size-4" />
            )}
            {released ? "Format is clean" : "Needs a look"}
          </p>
          <p className="mt-0.5 text-sm text-coffee-600">
            {released
              ? "Compiled and verified from the real PDF — no blocking issues."
              : measured
                ? "The CV compiled, but some issues still need your attention."
                : "The document couldn't be compiled here, so it wasn't verified."}
          </p>
        </div>
      </div>

      {/* What we fixed */}
      <section className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-sm font-semibold text-coffee-800">
          <Wand2 className="size-4 text-coffee-500" />
          {delta.fixed.length > 0
            ? `Fixed automatically · ${delta.fixed.length}`
            : "Nothing to fix"}
        </h4>
        {delta.fixed.length > 0 ? (
          <ul className="space-y-2">
            {delta.fixed.map((f, i) => (
              <li
                key={`${f.field}-${i}`}
                className="rounded-md border border-coffee-200 bg-white p-3 text-sm"
              >
                <div className="flex items-center gap-2 text-xs font-medium text-coffee-500">
                  <span className="rounded bg-coffee-100 px-1.5 py-0.5">
                    {ruleLabel(f.rule_id)}
                  </span>
                  <span className="truncate text-coffee-400">{f.field}</span>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <span className="text-coffee-400 line-through">{f.before}</span>
                  <span className="text-coffee-400">→</span>
                  <span className="font-medium text-coffee-800">{f.after}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-coffee-500">
            No formatting problems were found in your CV.
          </p>
        )}
      </section>

      {/* Remaining issues */}
      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-coffee-800">
          {remaining.length > 0
            ? `Still needs attention · ${remaining.length}`
            : "No remaining issues"}
        </h4>
        {remaining.length > 0 ? (
          <ul className="space-y-2">
            {remaining.map((v, i) => (
              <li
                key={`${v.rule_id}-${i}`}
                className={
                  v.severity === "minor"
                    ? "rounded-md border border-coffee-200 bg-white p-3 text-sm"
                    : "rounded-md border border-amber-200 bg-amber-50 p-3 text-sm"
                }
              >
                <p className="flex items-center gap-2 font-medium text-coffee-800">
                  <span
                    className={
                      v.severity === "minor"
                        ? "rounded bg-coffee-100 px-1.5 py-0.5 text-xs text-coffee-600"
                        : "rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800"
                    }
                  >
                    {v.severity}
                  </span>
                  {v.message}
                </p>
                {v.fix_hint && (
                  <p className="mt-1 text-xs text-coffee-500">{v.fix_hint}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-1.5 text-sm text-green-700">
            <CheckCircle2 className="size-4" />
            Everything checks out.
          </p>
        )}
      </section>
    </div>
  );
}
