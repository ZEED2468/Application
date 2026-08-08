import { Sparkles, Target, ThumbsUp } from "lucide-react";
import type { CvRunResult } from "@jd/shared-types";

/** Advisory LLM judgment on a run (Slice 6): semantic JD-coverage + an overall fit read.
 *  Second, on the deterministic floor — it never changed the score or release. */
export function RunJudgment({ run }: { run: CvRunResult }) {
  const judgment = run.judgment;
  if (!judgment) {
    return (
      <p className="text-sm text-coffee-500">
        No AI judgment for this run — attach a job description and configure an LLM to see a
        coverage + fit read.
      </p>
    );
  }
  const { coverage, fit } = judgment;

  return (
    <div className="space-y-6">
      {/* Fit verdict */}
      <div className="flex items-start gap-3 rounded-lg border border-coffee-200 bg-white p-4">
        <ThumbsUp className="mt-0.5 size-5 text-coffee-500" />
        <div className="min-w-0">
          <p className="font-semibold text-coffee-800">{fit.verdict || "Fit read"}</p>
          {fit.fit_summary && (
            <p className="mt-0.5 text-sm text-coffee-600">{fit.fit_summary}</p>
          )}
        </div>
      </div>

      {/* JD coverage */}
      <section className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-sm font-semibold text-coffee-800">
          <Target className="size-4 text-coffee-500" />
          JD coverage
        </h4>
        {coverage.summary && (
          <p className="text-sm text-coffee-600">{coverage.summary}</p>
        )}
        {coverage.semantic_covered.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-green-700">Covered under another name</p>
            <ul className="space-y-1">
              {coverage.semantic_covered.map((c, i) => (
                <li
                  key={`${c.keyword}-${i}`}
                  className="rounded-md border border-green-200 bg-green-50 p-2 text-sm"
                >
                  <span className="font-medium text-green-800">{c.keyword}</span>
                  <span className="text-coffee-500"> — “{c.evidence}”</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {coverage.still_missing.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-amber-700">Still missing</p>
            <div className="flex flex-wrap gap-1.5">
              {coverage.still_missing.map((k) => (
                <span
                  key={k}
                  className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
                >
                  {k}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Strengths / gaps / recommendations */}
      {fit.strengths.length > 0 && (
        <section className="space-y-1.5">
          <h4 className="flex items-center gap-1.5 text-sm font-semibold text-coffee-800">
            <ThumbsUp className="size-4 text-coffee-500" />
            Strengths
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {fit.strengths.map((s, i) => (
              <span
                key={`${s}-${i}`}
                className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-800"
              >
                {s}
              </span>
            ))}
          </div>
        </section>
      )}
      {fit.gaps.length > 0 && (
        <section className="space-y-1.5">
          <h4 className="text-sm font-semibold text-coffee-800">Gaps</h4>
          <ul className="space-y-1.5">
            {fit.gaps.map((g, i) => (
              <li
                key={`${g.skill}-${i}`}
                className="rounded-md border border-coffee-200 bg-white p-2.5 text-sm"
              >
                <p className="flex items-center gap-2 font-medium text-coffee-800">
                  <span className="rounded bg-coffee-100 px-1.5 py-0.5 text-xs text-coffee-600">
                    {g.severity}
                  </span>
                  {g.skill}
                </p>
                {g.reason && <p className="mt-0.5 text-xs text-coffee-500">{g.reason}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {fit.recommendations.length > 0 && (
        <section className="space-y-1.5">
          <h4 className="flex items-center gap-1.5 text-sm font-semibold text-coffee-800">
            <Sparkles className="size-4 text-coffee-500" />
            Recommendations
          </h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-coffee-600">
            {fit.recommendations.map((r, i) => (
              <li key={`${r}-${i}`}>{r}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
