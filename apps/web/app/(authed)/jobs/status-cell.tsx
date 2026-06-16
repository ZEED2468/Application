"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { JobOut, TrackerStatus } from "@jd/shared-types";
import { TRACKER_STATUSES } from "@jd/shared-types";
import { applicationsService, type JobsFilter } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { STATUS_LABELS, STATUS_TINT } from "@/lib/status";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export function StatusCell({
  job,
  filter,
}: {
  job: JobOut;
  filter: JobsFilter;
}) {
  const queryClient = useQueryClient();
  const jobsKey = ["jobs", filter] as const;

  const mutation = useMutation({
    mutationFn: async (status: TrackerStatus) => {
      if (!job.application_id) {
        throw Object.assign(new Error("No application yet"), { status: 0 });
      }
      await applicationsService.setStatus(job.application_id, status);
      return status;
    },
    onMutate: async (status) => {
      await queryClient.cancelQueries({ queryKey: jobsKey });
      const prev = queryClient.getQueryData<JobOut[]>(jobsKey);
      queryClient.setQueryData<JobOut[]>(jobsKey, (old) =>
        (old ?? []).map((j) =>
          j.id === job.id ? { ...j, application_status: status } : j,
        ),
      );
      return { prev };
    },
    onError: async (err, _status, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(jobsKey, ctx.prev);
      const e = await toApiError(err);
      toast.error(
        e.status === 0 && !job.application_id
          ? "This job has no application yet — generate it first."
          : `Couldn't update status: ${e.message}`,
      );
    },
    onSuccess: (status) => {
      toast.success(`Marked as ${STATUS_LABELS[status]}`);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: jobsKey });
    },
  });

  const current = job.application_status;
  const disabled = !job.application_id || mutation.isPending;

  return (
    <div
      className="flex items-center gap-2"
      onClick={(e) => e.stopPropagation()}
    >
      {current && (
        <span
          className={cn("size-2 shrink-0 rounded-full", STATUS_TINT[current].dot)}
        />
      )}
      <Select
        selectSize="sm"
        value={current ?? ""}
        disabled={disabled}
        onChange={(e) => mutation.mutate(e.target.value as TrackerStatus)}
        className="min-w-36"
        aria-label="Application status"
      >
        {!current && (
          <option value="" disabled>
            —
          </option>
        )}
        {TRACKER_STATUSES.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABELS[s]}
          </option>
        ))}
      </Select>
    </div>
  );
}
