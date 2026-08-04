"use client";

import * as React from "react";
import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Sparkles } from "lucide-react";
import type { LatexKind, Track } from "@jd/shared-types";
import { atsService, jobsService, latexService } from "@/lib/api/services";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import { PageHeading, ErrorState } from "@/components/states";
import { LatexBuilder } from "@/components/latex-builder";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default function JobBuilderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const [active, setActive] = React.useState<LatexKind>("cv");
  const [cvLatex, setCvLatex] = React.useState("");
  const [coverLatex, setCoverLatex] = React.useState("");
  const [note, setNote] = React.useState<string | null>(null);
  const autoRan = React.useRef(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.job(id),
    queryFn: () => jobsService.detail(id),
  });

  const regenerate = useMutation({
    mutationFn: async () => {
      const job = data!.job;
      // Recommendations come from the persisted ATS analysis for this job (from the DB,
      // not a browser handoff) — undefined if no ATS check has been run for it yet.
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

  // Effortless path: regenerate once on first load (recs are read from the persisted analysis).
  React.useEffect(() => {
    if (data && !autoRan.current) {
      autoRan.current = true;
      regenerate.mutate();
    }
  }, [data, id, regenerate]);

  const useCv = useMutation({
    mutationFn: (latex: string) => jobsService.setCvFromLatex(id, latex),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
      toast.success("CV updated for this job.");
      router.push(`/jobs/${id}`);
    },
    onError: (err) => toastApiError(err),
  });

  const useCover = useMutation({
    mutationFn: (latex: string) => jobsService.setCoverFromLatex(id, latex),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) });
      toast.success("Cover letter updated for this job.");
      router.push(`/jobs/${id}`);
    },
    onError: (err) => toastApiError(err),
  });

  if (isError) {
    return (
      <div className="space-y-6">
        <BackLink id={id} />
        <ErrorState
          title="Couldn't load this job"
          description="It may not exist, or the backend is offline."
          retry={() => refetch()}
        />
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <BackLink id={id} />
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-[68vh]" />
      </div>
    );
  }

  const { job } = data;

  return (
    <div className="space-y-5">
      <BackLink id={id} />
      <PageHeading
        title="LaTeX builder"
        description={`${job.role} · ${job.company}`}
        actions={
          <Button
            variant="accent"
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
          >
            <Sparkles className="size-4" />
            {regenerate.isPending ? "Regenerating…" : "Regenerate"}
          </Button>
        }
      />

      {note && (
        <p className="rounded-md border border-coffee-200 bg-coffee-100/50 px-3 py-2 text-sm text-coffee-700">
          {note}
        </p>
      )}

      <div className="flex items-center gap-1.5">
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
        {regenerate.isPending && (
          <span className="ml-2 text-xs text-coffee-400">Tailoring from your profile…</span>
        )}
      </div>

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

function BackLink({ id }: { id: string }) {
  return (
    <Link
      href={`/jobs/${id}`}
      className="inline-flex items-center gap-1.5 text-sm text-coffee-500 hover:text-coffee-700"
    >
      <ArrowLeft className="size-4" />
      Back to job
    </Link>
  );
}
