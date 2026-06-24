"use client";

import { Eye, ExternalLink } from "lucide-react";
import { absoluteApiUrl } from "@/lib/api/client";

export function DocLinkCell({
  url,
  label,
  onPreview,
}: {
  url: string | null | undefined;
  label: string;
  /** when provided, the cell previews in-app instead of opening a new tab */
  onPreview?: (url: string) => void;
}) {
  if (!url) return null;

  if (onPreview) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onPreview(url);
        }}
        title={`Preview ${label}`}
        className="inline-flex items-center gap-1 text-sm font-medium text-coffee-700 underline underline-offset-2 hover:text-coffee-900"
      >
        <Eye className="size-3.5 shrink-0" />
        Preview
      </button>
    );
  }

  const href = absoluteApiUrl(url);
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      title={`Open ${label}`}
      className="inline-flex items-center gap-1 text-sm font-medium text-coffee-700 underline underline-offset-2 hover:text-coffee-900"
      onClick={(e) => e.stopPropagation()}
    >
      Open
      <ExternalLink className="size-3.5 shrink-0" />
    </a>
  );
}
