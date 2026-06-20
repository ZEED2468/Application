"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { JobOut, TrackerStatus } from "@jd/shared-types";
import { TRACKER_STATUSES_POST_SUBMIT } from "@jd/shared-types";
import { jobsService, type JobsFilter } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { toApiError } from "@/lib/api/client";
import { STATUS_LABELS, STATUS_TINT } from "@/lib/status";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

type StatusJob = Pick<
  JobOut,
  "id" | "application_id" | "application_status"
>;

export function StatusCell({
  job,
  filter,
  jobDetailId,
}: {
  job: StatusJob;
  filter?: JobsFilter;
  /** When set, also refresh the job detail query after a status change. */
  jobDetailId?: string;
}) {
  const queryClient = useQueryClient();
  const jobsKey = queryKeys.jobs(filter ?? {});

  const current: TrackerStatus = job.application_status ?? "not_applied";

  const mutation = useMutation({
    mutationFn: async (status: TrackerStatus) => {
      if (status === "not_applied") {
        throw Object.assign(new Error("Cannot revert to not applied"), {
          status: 0,
        });
      }
      return jobsService.setApplicationStatus(job.id, status);
    },
    onMutate: async (status) => {
      await queryClient.cancelQueries({ queryKey: jobsKey });
      const prev = queryClient.getQueryData<JobOut[]>(jobsKey);
      queryClient.setQueryData<JobOut[]>(jobsKey, (old) =>
        (old ?? []).map((j) =>
          j.id === job.id
            ? {
                ...j,
                application_status: status,
                application_id: j.application_id ?? "pending",
              }
            : j,
        ),
      );
      return { prev };
    },
    onError: async (err, _status, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(jobsKey, ctx.prev);
      const e = await toApiError(err);
      toast.error(`Couldn't update status: ${e.message}`);
    },
    onSuccess: (updated, status) => {
      toast.success(`Marked as ${STATUS_LABELS[status]}`);
      if (updated) {
        queryClient.setQueryData<JobOut[]>(jobsKey, (old) =>
          (old ?? []).map((j) => (j.id === job.id ? { ...j, ...updated } : j)),
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: jobsKey });
      if (jobDetailId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.job(jobDetailId) });
      }
    },
  });

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
        className="min-w-40"
        aria-label="Application status"
      >
        {current === "not_applied" && (
          <option value="not_applied" disabled>
            {STATUS_LABELS.not_applied}
          </option>
        )}
        {TRACKER_STATUSES_POST_SUBMIT.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABELS[s]}
          </option>
        ))}
      </Select>
    </div>
  );
}
