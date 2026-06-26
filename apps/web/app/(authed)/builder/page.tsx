"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Sparkles } from "lucide-react";
import type { LatexKind, RegenerateAtsRecs, Track } from "@jd/shared-types";
import { latexService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { PageHeading } from "@/components/states";
import { LatexBuilder } from "@/components/latex-builder";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

interface StandalonePayload {
  track?: Track | null;
  jd_text?: string | null;
  role_title?: string | null;
  ats?: RegenerateAtsRecs;
}

export default function StandaloneBuilderPage() {
  const [active, setActive] = React.useState<LatexKind>("cv");
  const [cvLatex, setCvLatex] = React.useState("");
  const [coverLatex, setCoverLatex] = React.useState("");
  const [payload, setPayload] = React.useState<StandalonePayload | null>(null);
  const [ready, setReady] = React.useState(false);
  const autoRan = React.useRef(false);

  React.useEffect(() => {
    const track =
      (new URLSearchParams(window.location.search).get("track") as Track | null) ??
      null;
    let stashed: StandalonePayload = {};
    const raw = window.sessionStorage.getItem("latex-regen-standalone");
    if (raw) {
      window.sessionStorage.removeItem("latex-regen-standalone");
      try {
        stashed = JSON.parse(raw) as StandalonePayload;
      } catch {
        stashed = {};
      }
    }
    setPayload({ ...stashed, track: stashed.track ?? track });
    setReady(true);
  }, []);

  const regenerate = useMutation({
    mutationFn: () =>
      latexService.regenerate({
        track: payload?.track ?? null,
        jd_text: payload?.jd_text ?? null,
        role_title: payload?.role_title ?? null,
        ats: payload?.ats,
      }),
    onSuccess: (res) => {
      setCvLatex(res.cv_latex);
      setCoverLatex(res.cover_latex);
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  React.useEffect(() => {
    if (ready && payload?.track && !autoRan.current) {
      autoRan.current = true;
      regenerate.mutate();
    }
  }, [ready, payload, regenerate]);

  return (
    <div className="space-y-5">
      <Link
        href="/ats-checker"
        className="inline-flex items-center gap-1.5 text-sm text-coffee-500 hover:text-coffee-700"
      >
        <ArrowLeft className="size-4" />
        Back to ATS Checker
      </Link>

      <PageHeading
        title="LaTeX builder"
        description="Draft a tailored CV + cover letter in your template, then preview and download. To attach it to a job, open the builder from that job instead."
        actions={
          payload?.track ? (
            <Button
              variant="accent"
              onClick={() => regenerate.mutate()}
              disabled={regenerate.isPending}
            >
              <Sparkles className="size-4" />
              {regenerate.isPending ? "Regenerating…" : "Regenerate"}
            </Button>
          ) : undefined
        }
      />

      {ready && !payload?.track ? (
        <p className="rounded-md border border-coffee-200 bg-coffee-100/50 px-4 py-3 text-sm text-coffee-700">
          Run an ATS check first, then click “Regenerate CV” to land here with your
          recommendations. <Link href="/ats-checker" className="underline">Open ATS Checker</Link>.
        </p>
      ) : (
        <>
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
              <span className="ml-2 text-xs text-coffee-400">
                Tailoring from your profile…
              </span>
            )}
          </div>

          <div className={cn(active !== "cv" && "hidden")}>
            <LatexBuilder
              kind="cv"
              value={cvLatex}
              onChange={setCvLatex}
              disabled={regenerate.isPending}
            />
          </div>
          <div className={cn(active !== "cover" && "hidden")}>
            <LatexBuilder
              kind="cover"
              value={coverLatex}
              onChange={setCoverLatex}
              disabled={regenerate.isPending}
            />
          </div>
        </>
      )}
    </div>
  );
}
