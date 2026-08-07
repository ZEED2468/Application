import type { CvRunResult } from "@jd/shared-types";
import { api, path } from "../client";

export const cvRunsService = {
  /** Run the CV engine for a job (format check + deterministic fixes). */
  async runForJob(jobId: string): Promise<CvRunResult> {
    return api
      .post(path(`/api/cv/runs/job/${jobId}`))
      .json<CvRunResult>();
  },
};
