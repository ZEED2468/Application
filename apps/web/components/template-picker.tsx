"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Eye, Upload } from "lucide-react";
import type { Track } from "@jd/shared-types";
import {
  cvTemplatesService,
  templatePreviewPath,
} from "@/lib/api/services/cv-templates";
import { absoluteApiUrl } from "@/lib/api/client";
import { toastApiError } from "@/lib/toast-error";

/** Per-track CV template: pick a built-in or a validated custom .tex; the engine resolves it. */
export function TemplatePicker({ track }: { track: Track }) {
  const qc = useQueryClient();
  const fileRef = React.useRef<HTMLInputElement>(null);
  const key = ["cv-templates", track];

  const q = useQuery({ queryKey: key, queryFn: () => cvTemplatesService.list(track) });
  const bound = q.data?.bound ?? "canonical";

  const bind = useMutation({
    mutationFn: (id: string) => cvTemplatesService.bind(track, id),
    onSuccess: () => {
      toast.success("Template updated for this track");
      qc.invalidateQueries({ queryKey: key });
    },
    onError: (e) => toastApiError(e),
  });

  const upload = useMutation({
    mutationFn: (file: File) =>
      cvTemplatesService.upload(track, file.name.replace(/\.[^.]+$/, ""), file),
    onSuccess: (res) => {
      toast.success("Custom template validated and added");
      qc.invalidateQueries({ queryKey: key });
      bind.mutate(res.id);
    },
    onError: (e) => toastApiError(e, "That template didn't pass validation"),
  });

  const preview = absoluteApiUrl(templatePreviewPath(bound));

  return (
    <div className="space-y-2 rounded-md border border-coffee-100 p-3">
      <div className="flex items-center justify-between gap-2">
        <label className="text-sm font-medium text-coffee-800">CV template</label>
        {preview && (
          <a
            href={preview}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-coffee-600 underline underline-offset-2 hover:text-coffee-900"
          >
            <Eye className="size-3.5" /> Preview
          </a>
        )}
      </div>
      <select
        value={bound}
        disabled={bind.isPending || q.isLoading}
        onChange={(e) => bind.mutate(e.target.value)}
        className="w-full rounded-md border border-coffee-200 bg-white px-3 py-2 text-sm"
      >
        {(q.data?.templates ?? []).map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
            {t.source === "custom" ? " (custom)" : ""}
          </option>
        ))}
      </select>
      <div>
        <input
          ref={fileRef}
          type="file"
          accept=".tex,.txt"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
            e.currentTarget.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={upload.isPending}
          className="inline-flex items-center gap-1.5 text-xs text-coffee-600 underline underline-offset-2 hover:text-coffee-900"
        >
          <Upload className="size-3.5" />
          {upload.isPending ? "Validating…" : "Upload a custom .tex (with %%CV:…%% slots)"}
        </button>
      </div>
    </div>
  );
}
