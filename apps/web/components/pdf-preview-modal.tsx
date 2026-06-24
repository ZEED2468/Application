"use client";

import * as React from "react";
import { X } from "lucide-react";
import { absoluteApiUrl } from "@/lib/api/client";

/**
 * In-app PDF preview. Renders the auth-scoped download endpoint (which 307-redirects
 * to a presigned, inline R2 URL) inside an iframe — so a VA can review the CV/cover
 * without leaving the app.
 */
export function PdfPreviewModal({
  open,
  onClose,
  title,
  url,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  url: string | null | undefined;
}) {
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  const src = absoluteApiUrl(url);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="absolute inset-0 bg-coffee-900/40" onClick={onClose} />
      <div className="relative z-10 flex h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-coffee-300 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-coffee-100 px-5 py-3">
          <h2 className="truncate text-sm font-semibold text-coffee-900">{title}</h2>
          <div className="flex shrink-0 items-center gap-4">
            {src && (
              <a
                href={src}
                target="_blank"
                rel="noreferrer noopener"
                className="text-xs text-coffee-500 underline underline-offset-4 hover:text-coffee-900"
              >
                Open / download
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close preview"
              className="text-coffee-500 hover:text-coffee-900"
            >
              <X className="size-5" />
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 bg-coffee-50">
          {src ? (
            <iframe src={src} title={title} className="h-full w-full" />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-coffee-400">
              Not generated yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
