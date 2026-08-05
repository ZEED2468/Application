"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import type { LatexKind, Track } from "@jd/shared-types";
import { atsService, jobsService, latexService } from "@/lib/api/services";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import { LatexBuilder } from "@/components/latex-builder";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The job-bound LaTeX editor — regenerate a tailored draft (into the user's template),
 * tweak it with a live PDF preview, then commit it to the job. Used inline in the
 * résumé workspace; `onCommitted` fires after a successful CV/cover commit so the
 * caller can return to the rendered view.
 */
export function ResumeEditor({
  id,
  onCommitted,
}: {
  id: string;
  onCommitted?: () => void;
}) {
  const queryClient = useQueryClient();
  const [active, setActive] = React.useState<LatexKind>("cv");
  const [cvLatex, setCvLatex] = React.useState("");
  const [coverLatex, setCoverLatex] = React.useState("");
  const [note, setNote] = React.useState<string | null>(null);
  const loaded = React.useRef(false);

  // Shares the job query with the workspace (react-query dedupes it — no extra fetch).
  const { data } = useQuery({
    queryKey: queryKeys.job(id),
    queryFn: () => jobsService.detail(id),
  });

  const regenerate = useMutation({
    mutationFn: async () => {
      const job = data!.job;
      // Recommendations come from the persisted ATS analysis for this job (from the DB),
      // undefined if no ATS check has been run for it yet.
      const recs = (await atsService.latestRecs(id)) ?? undefined;
      return latexService.regenerate({
        job_id: id,
        track: job.track as Track,
        jd_text: job.jd_text ?? job.description ?? null,
        role_title: job.role,
        ats: recs,
      });
    },
    onSuccess: (res) => {
      setCvLatex(res.cv_latex);
      setCoverLatex(res.cover_latex);
      if (res.cv_fell_back === "no_template") {
        setNote(
          "Rendered with the default layout — upload a LaTeX template on your Profile to use your own design.",
        );
      } else if (res.cv_compiled === false) {
        // Honor-or-explain: we kept your template but the tailored CV didn't compile.
        setNote(
          `Couldn't fully render into your template. Compiler error: ${(res.cv_stderr ?? "").slice(0, 300)} — edit the LaTeX below and click "Compile preview".`,
        );
        toast.error("CV couldn't be rendered into your template — fix the error shown below.");
      } else {
        setNote(null);
      }
    },
    onError: (err) => toastApiError(err),
  });

  // Open with YOUR committed résumé so editing tweaks the current CV (no auto-LLM, no
  // lost edits). Regenerate is an explicit choice. The cover's LaTeX isn't stored, so
  // it stays blank until you regenerate.
  React.useEffect(() => {
    if (loaded.current || !data) return;
    loaded.current = true;
    const src = data.generated_cv?.latex_source;
    if (src) setCvLatex(src);
  }, [data]);

  const useCv = useMutation({
    mutationFn: (latex: string) => jobsService.setCvFromLatex(id, latex),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
      toast.success("CV updated for this job.");
      onCommitted?.();
    },
    onError: (err) => toastApiError(err),
  });

  const useCover = useMutation({
    mutationFn: (latex: string) => jobsService.setCoverFromLatex(id, latex),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
      toast.success("Cover letter updated for this job.");
      onCommitted?.();
    },
    onError: (err) => toastApiError(err),
  });

  return (
    <div className="flex flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {(["cv", "cover"] as LatexKind[]).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setActive(k)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm transition-colors",
              active === k
                ? "bg-coffee-700 font-medium text-cream"
                : "border border-coffee-200 text-coffee-700 hover:bg-coffee-100",
            )}
          >
            {k === "cv" ? "CV" : "Cover letter"}
          </button>
        ))}
        <Button
          variant="accent"
          size="sm"
          className="ml-auto"
          onClick={() => regenerate.mutate()}
          disabled={regenerate.isPending}
        >
          <Sparkles className="size-4" />
          {regenerate.isPending ? "Regenerating…" : "Regenerate"}
        </Button>
      </div>

      {note && (
        <p className="rounded-md border border-coffee-200 bg-coffee-100/50 px-3 py-2 text-sm text-coffee-700">
          {note}
        </p>
      )}

      <div className={cn(active !== "cv" && "hidden")}>
        <LatexBuilder
          kind="cv"
          value={cvLatex}
          onChange={setCvLatex}
          onUse={(latex) => useCv.mutate(latex)}
          useLabel="Use this CV"
          busy={useCv.isPending}
          disabled={regenerate.isPending}
        />
      </div>
      <div className={cn(active !== "cover" && "hidden")}>
        <LatexBuilder
          kind="cover"
          value={coverLatex}
          onChange={setCoverLatex}
          onUse={(latex) => useCover.mutate(latex)}
          useLabel="Use this cover letter"
          busy={useCover.isPending}
          disabled={regenerate.isPending}
        />
      </div>
    </div>
  );
}
