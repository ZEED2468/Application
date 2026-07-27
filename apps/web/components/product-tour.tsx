"use client";

import * as React from "react";
import { X, ArrowRight, ArrowLeft } from "lucide-react";

export interface TourStep {
  /** CSS selector of the element to highlight; omit for a centered step (welcome). */
  selector?: string;
  title: string;
  body: string;
}

const PAD = 6; // spotlight padding around the target

/**
 * A lightweight interactive product tour: a dimmed overlay that "spotlights" a
 * target element (via a big box-shadow) and shows a positioned tooltip with
 * Back / Next / Skip. Steps without a selector render as a centered card (welcome).
 */
export function ProductTour({
  steps,
  open,
  onClose,
}: {
  steps: TourStep[];
  open: boolean;
  onClose: () => void;
}) {
  const [i, setI] = React.useState(0);
  const [rect, setRect] = React.useState<DOMRect | null>(null);

  React.useEffect(() => {
    if (open) setI(0);
  }, [open]);

  const step = steps[i];

  React.useLayoutEffect(() => {
    if (!open || !step?.selector) {
      setRect(null);
      return;
    }
    const el = document.querySelector(step.selector) as HTMLElement | null;
    if (!el) {
      setRect(null);
      return;
    }
    const update = () => setRect(el.getBoundingClientRect());
    el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, step?.selector, i]);

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !step) return null;

  const isLast = i === steps.length - 1;
  const next = () => (isLast ? onClose() : setI((n) => Math.min(n + 1, steps.length - 1)));
  const back = () => setI((n) => Math.max(n - 1, 0));

  // Tooltip position: under the target, else centered.
  const tip: React.CSSProperties = rect
    ? {
        position: "fixed",
        top: Math.min(rect.bottom + 10, window.innerHeight - 220),
        left: Math.min(Math.max(rect.left, 12), window.innerWidth - 340),
        width: 320,
      }
    : {
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: 380,
      };

  return (
    <div className="fixed inset-0 z-[60]" aria-live="polite">
      {/* Dim + spotlight */}
      {rect ? (
        <div
          style={{
            position: "fixed",
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            borderRadius: 10,
            boxShadow: "0 0 0 9999px rgba(41, 30, 20, 0.55)",
            pointerEvents: "none",
            transition: "all 120ms ease",
          }}
        />
      ) : (
        <div className="fixed inset-0 bg-coffee-900/55" />
      )}

      {/* Tooltip / card */}
      <div
        style={tip}
        className="z-[61] rounded-lg border border-coffee-300 bg-white p-4 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-sm font-semibold text-coffee-900">{step.title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Skip tour"
            className="shrink-0 text-coffee-400 hover:text-coffee-700"
          >
            <X className="size-4" />
          </button>
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-coffee-600">{step.body}</p>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs text-coffee-400">
            {i + 1} / {steps.length}
          </span>
          <div className="flex items-center gap-2">
            {i > 0 && (
              <button
                type="button"
                onClick={back}
                className="inline-flex items-center gap-1 rounded-md border border-coffee-300 px-2.5 py-1.5 text-xs text-coffee-700 hover:bg-coffee-100"
              >
                <ArrowLeft className="size-3.5" />
                Back
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-2.5 py-1.5 text-xs text-coffee-500 hover:text-coffee-900"
            >
              Skip
            </button>
            <button
              type="button"
              onClick={next}
              className="inline-flex items-center gap-1 rounded-md bg-coffee-700 px-3 py-1.5 text-xs font-medium text-cream hover:bg-coffee-900"
            >
              {isLast ? "Finish" : "Next"}
              {!isLast && <ArrowRight className="size-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
