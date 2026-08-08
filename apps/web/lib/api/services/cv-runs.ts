import type { CvRunResult } from "@jd/shared-types";
import { api, path } from "../client";

export const cvRunsService = {
  /** Run the CV engine for a job (format check + deterministic fixes). */
  async runForJob(jobId: string): Promise<CvRunResult> {
    return api
      .post(path(`/api/cv/runs/job/${jobId}`))
      .json<CvRunResult>();
  },

  /** Revamp a track's stored source CV: parse it and re-render it clean through the engine. */
  async revampTrack(track: string): Promise<CvRunResult> {
    return api
      .post(path(`/api/cv/runs/revamp/track/${track}`))
      .json<CvRunResult>();
  },
};
