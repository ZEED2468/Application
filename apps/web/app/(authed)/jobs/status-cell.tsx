"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { JobOut, TrackerStatus } from "@jd/shared-types";
import { TRACKER_STATUSES_POST_SUBMIT } from "@jd/shared-types";
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

  const current: TrackerStatus =
    job.application_status ?? "not_applied";
  const hasApplication = Boolean(job.application_id);

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
      toast.error(`Couldn't update status: ${e.message}`);
    },
    onSuccess: (status) => {
      toast.success(`Marked as ${STATUS_LABELS[status]}`);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: jobsKey });
    },
  });

  if (!hasApplication) {
    return (
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 shrink-0 rounded-full",
            STATUS_TINT.not_applied.dot,
          )}
        />
        <span className="text-sm text-coffee-500">
          {STATUS_LABELS.not_applied}
        </span>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-2"
      onClick={(e) => e.stopPropagation()}
    >
      <span
        className={cn("size-2 shrink-0 rounded-full", STATUS_TINT[current].dot)}
      />
      <Select
        selectSize="sm"
        value={current}
        disabled={mutation.isPending}
        onChange={(e) => mutation.mutate(e.target.value as TrackerStatus)}
        className="min-w-36"
        aria-label="Application status"
      >
        {TRACKER_STATUSES_POST_SUBMIT.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABELS[s]}
          </option>
        ))}
      </Select>
    </div>
  );
}
