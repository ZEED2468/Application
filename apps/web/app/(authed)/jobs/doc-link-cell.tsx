"use client";

import { ExternalLink } from "lucide-react";
import { absoluteApiUrl } from "@/lib/api/client";

export function DocLinkCell({
  url,
  label,
}: {
  url: string | null | undefined;
  label: string;
}) {
  const href = absoluteApiUrl(url);

  if (!href) {
    return null;
  }

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
