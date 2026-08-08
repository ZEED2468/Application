import { History } from "lucide-react";
import type { CvRunStep } from "@jd/shared-types";

const STATE_LABEL: Record<string, string> = {
  ingested: "Ingested",
  gap_analyzed: "Gap check",
  diagnosed: "Diagnosed",
  patching: "Patched",
  recompiled: "Rendered",
  verified: "Verified",
  judged: "Judged",
  released: "Released",
  needs_input: "Needs input",
  needs_review: "Needs review",
};

/** The run's ordered step trail (Slice 8): the "why did it change this" audit surface,
 *  each step labeled with the model / prompt version where an LLM was involved. */
export function RunTrail({ steps }: { steps: CvRunStep[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-coffee-500">No steps recorded for this run.</p>;
  }
  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-1.5 text-sm font-semibold text-coffee-800">
        <History className="size-4 text-coffee-500" />
        Pipeline trail · {steps.length}
      </h4>
      <ol className="space-y-1.5">
        {steps.map((s, i) => (
          <li
            key={`${s.state}-${i}`}
            className="flex items-center justify-between gap-2 rounded-md border border-coffee-200 bg-white px-3 py-2 text-sm"
          >
            <span className="flex items-center gap-2">
              <span className="text-xs text-coffee-400">{i + 1}</span>
              <span className="font-medium text-coffee-800">
                {STATE_LABEL[s.state] ?? s.state}
              </span>
              {s.prompt_version && (
                <span className="rounded bg-coffee-100 px-1.5 py-0.5 text-xs text-coffee-500">
                  {s.model ? `${s.model} · ` : ""}
                  {s.prompt_version}
                </span>
              )}
            </span>
            {s.duration_ms != null && (
              <span className="text-xs text-coffee-400">{s.duration_ms} ms</span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
