"use client";

import { ExternalLink } from "lucide-react";
import { toGoogleDocsViewerUrl } from "@/lib/docs-links";

export function DocLinkCell({
  url,
  label,
}: {
  url: string | null | undefined;
  label: string;
}) {
  const href = toGoogleDocsViewerUrl(url);

  if (!href) {
    return null;
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      title={`Open ${label} in Google Docs viewer`}
      className="inline-flex items-center gap-1 text-sm font-medium text-coffee-700 underline underline-offset-2 hover:text-coffee-900"
      onClick={(e) => e.stopPropagation()}
    >
      Google Doc
      <ExternalLink className="size-3.5 shrink-0" />
    </a>
  );
}
