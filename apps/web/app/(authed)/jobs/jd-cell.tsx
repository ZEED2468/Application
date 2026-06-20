"use client";

import * as React from "react";
import type { JobOut } from "@jd/shared-types";
import { JdModal } from "@/components/jd-modal";
import { jdPreview } from "@/lib/docs-links";

export function JdCell({ job }: { job: JobOut }) {
  const [open, setOpen] = React.useState(false);
  const preview = job.jd_preview ?? jdPreview(job.description);
  const full = job.description?.trim();

  if (!full) {
    return <span className="text-sm text-coffee-300">—</span>;
  }

  return (
    <>
      <div
        className="min-w-0 space-y-1"
        onClick={(e) => e.stopPropagation()}
      >
        {preview && (
          <p className="line-clamp-3 text-sm leading-relaxed text-coffee-500">
            {preview}
          </p>
        )}
        <button
          type="button"
          className="text-sm font-medium text-coffee-700 underline underline-offset-2 hover:text-coffee-900"
          onClick={() => setOpen(true)}
        >
          View more
        </button>
      </div>
      <JdModal
        open={open}
        onClose={() => setOpen(false)}
        title={job.role}
        company={job.company}
        description={full}
      />
    </>
  );
}
