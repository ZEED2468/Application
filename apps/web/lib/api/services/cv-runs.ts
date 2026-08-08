import type { CvRunDetail, CvRunResult } from "@jd/shared-types";
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

  /** A run + its ordered step trail (the change-history / eval-pair surface). */
  async getRunDetail(runId: string): Promise<CvRunDetail> {
    return api.get(path(`/api/cv/runs/${runId}`)).json<CvRunDetail>();
  },
};
