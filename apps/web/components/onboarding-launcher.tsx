"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import type { MeResponse } from "@jd/shared-types";
import { authService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { ProductTour, type TourStep } from "@/components/product-tour";

const SEEN_KEY = "od:tour:v1";

/** Fire this event anywhere to (re)start the tour: window.dispatchEvent(new Event("od:start-tour")) */
export const START_TOUR_EVENT = "od:start-tour";

const STEPS: TourStep[] = [
  {
    title: "Welcome to The Outreach Desk",
    body:
      "Discover relevant jobs, generate a truth-bounded tailored CV + cover letter, check your ATS score, apply, and run recruiter outreach — all driven by your active track. Let's take a 30-second tour.",
  },
  {
    selector: '[data-tour="/jobs"]',
    title: "Jobs",
    body: "Roles matched to your tracks in Pipeline, and everything you've submitted in Submitted.",
  },
  {
    selector: '[data-tour="/ats-checker"]',
    title: "Tailor",
    body: "Score any CV against a job description, see keyword/tool gaps, then regenerate it in your own LaTeX template.",
  },
  {
    selector: '[data-tour="/profile"]',
    title: "Your Career Workspace",
    body: "Start here: create tracks, upload a resume per track, add templates and verified extras. A track needs a resume before AI features unlock.",
  },
  {
    selector: '[data-tour="/settings"]',
    title: "Bring your own AI key",
    body: "Add and validate your provider key (Anthropic, OpenAI-compatible, or Gemini). Encrypted at rest.",
  },
  {
    selector: '[data-tour="/help"]',
    title: "Help & setup checklist",
    body: "Your progress checklist and short guides live here — and you can replay this tour anytime.",
  },
];

export function OnboardingLauncher() {
  const { data: me } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
  const [open, setOpen] = React.useState(false);

  // First-login: auto-start once for hunters who haven't seen it.
  React.useEffect(() => {
    if (!me || me.type === "va" || typeof window === "undefined") return;
    if (window.localStorage.getItem(SEEN_KEY)) return;
    const t = window.setTimeout(() => setOpen(true), 500); // let the nav mount
    return () => window.clearTimeout(t);
  }, [me]);

  // Manual replay (e.g. from the Help page).
  React.useEffect(() => {
    const relaunch = () => setOpen(true);
    window.addEventListener(START_TOUR_EVENT, relaunch);
    return () => window.removeEventListener(START_TOUR_EVENT, relaunch);
  }, []);

  const close = React.useCallback(() => {
    setOpen(false);
    try {
      window.localStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* ignore */
    }
  }, []);

  return <ProductTour steps={STEPS} open={open} onClose={close} />;
}
