"use client";

import * as React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function JdModal({
  open,
  onClose,
  title,
  company,
  description,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  company: string;
  description: string;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="jd-modal-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-coffee-900/40"
        aria-label="Close"
        onClick={onClose}
      />
      <div
        className={cn(
          "relative z-10 flex max-h-[85vh] w-full max-w-2xl flex-col",
          "rounded-lg border border-coffee-300 bg-white shadow-lg",
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-coffee-100 px-6 py-4">
          <div>
            <h2 id="jd-modal-title" className="text-lg font-semibold text-coffee-900">
              {title}
            </h2>
            <p className="text-sm text-coffee-500">{company}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close job description"
          >
            <X className="size-4" />
          </Button>
        </div>
        <div className="overflow-y-auto px-6 py-4">
          <p className="whitespace-pre-wrap text-[0.95rem] leading-relaxed text-coffee-700">
            {description}
          </p>
        </div>
      </div>
    </div>
  );
}
