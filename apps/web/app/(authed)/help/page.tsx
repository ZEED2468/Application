"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, ArrowRight, Compass } from "lucide-react";
import { onboardingService } from "@/lib/api/services";
import { START_TOUR_EVENT } from "@/components/onboarding-launcher";
import { queryKeys } from "@/lib/query-keys";
import { PageHeading } from "@/components/states";
import { Accordion, type AccordionItemData } from "@/components/ui/accordion";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const dynamic = "force-dynamic";

const GUIDES: AccordionItemData[] = [
  {
    id: "overview",
    title: "Platform overview",
    content:
      "Discover relevant jobs, generate a truth-bounded tailored CV + cover letter, review the ATS analysis, apply, and run recruiter outreach — all driven by your active track. Nothing is ever fabricated: generation only uses facts from your CV, profile, verified extras, or what you confirm.",
  },
  {
    id: "ats-workflow",
    title: "The ATS optimization workflow",
    content:
      "Run a job description through the ATS Checker to see keyword coverage, tool gaps, structure/hygiene flags, weak-verb suggestions, and (with AI on) PAR/XYZ bullet coaching. Apply the truthful suggestions, then regenerate your CV in your LaTeX template.",
  },
  {
    id: "upload-cv",
    title: "Uploading a CV",
    content:
      "On Profile, pick your tracks and upload one source CV per track (PDF/Word). We extract and structure it into your master profile; review and confirm it.",
  },
  {
    id: "tracks",
    title: "Creating & using tracks",
    content:
      "A track (frontend / backend / general) owns its source CV, target roles, LaTeX templates, and preferences. Set your Active track on Profile — it drives which jobs and templates the dashboard prioritizes.",
  },
  {
    id: "latex",
    title: "LaTeX CV & cover-letter templates",
    content:
      "Upload your own .tex templates per track on Profile. When you regenerate from the ATS Checker, your tailored, truth-bounded content is rendered into that exact design; preview it side-by-side and use it on the job.",
  },
  {
    id: "verified-extras",
    title: "Verified extras & truth corpus",
    content:
      "Add genuinely-true skills, frameworks, tools, certifications, and projects that aren't on your CV. These join your truth corpus so tailoring can surface them — only add what's true.",
  },
  {
    id: "providers",
    title: "Configuring AI providers",
    content:
      "In Settings, add your own provider key (Anthropic, OpenAI, Gemini, or any OpenAI-compatible host like Groq/Together/OpenRouter/Ollama via a base URL). Mark one preferred and test the connection. Keys are encrypted at rest.",
  },
  {
    id: "ats-scores",
    title: "Understanding ATS scores",
    content:
      "The score is an internal keyword/coverage match optimized toward 90–95% — not a guarantee in any employer's ATS. Use the Resume Intelligence tabs to see exactly what's matched, missing, or omitted to stay truthful.",
  },
  {
    id: "applying",
    title: "Applying for jobs",
    content:
      "Open a job, review the JD + generated CV/cover + ATS, then Apply — it records the application, opens the posting, and surfaces the documents to attach. The read-only Tracker logs everything with credibility signals.",
  },
];

export default function HelpPage() {
  const status = useQuery({
    queryKey: queryKeys.onboardingStatus,
    queryFn: () => onboardingService.status(),
  });

  return (
    <div className="space-y-6">
      <PageHeading
        title="Help & getting started"
        description="Your setup checklist and short guides for every part of the platform."
        actions={
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event(START_TOUR_EVENT))}
            className="inline-flex items-center gap-1.5 rounded-md border border-coffee-300 px-3 py-1.5 text-sm text-coffee-700 hover:bg-coffee-100"
          >
            <Compass className="size-4" />
            Take the tour
          </button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Setup checklist</CardTitle>
          <CardDescription>
            Complete these to get the most out of the platform.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {status.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : status.data ? (
            <>
              {status.data.next_action && (
                <Link
                  href={status.data.next_action.href}
                  className="flex items-center gap-2 rounded-md border border-coffee-300 bg-coffee-100/50 px-3 py-2 text-sm font-medium text-coffee-900 hover:bg-coffee-100"
                >
                  <ArrowRight className="size-4 text-coffee-500" />
                  Next: {status.data.next_action.label}
                </Link>
              )}
              <ul className="space-y-2">
                {status.data.steps.map((s) => (
                  <li key={s.key}>
                    <Link
                      href={s.href}
                      className="flex items-center gap-2 text-sm text-coffee-700 hover:text-coffee-900"
                    >
                      {s.done ? (
                        <CheckCircle2 className="size-4 text-status-offer" />
                      ) : (
                        <Circle className="size-4 text-coffee-300" />
                      )}
                      <span className={s.done ? "line-through text-coffee-400" : ""}>
                        {s.label}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {status.data.complete && (
                <p className="text-sm text-status-offer">You&apos;re all set up. 🎉</p>
              )}
            </>
          ) : (
            <p className="text-sm text-coffee-400">Sign in to see your checklist.</p>
          )}
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-coffee-500">
          Guides
        </h2>
        <Accordion items={GUIDES} defaultOpen="overview" />
      </div>
    </div>
  );
}
