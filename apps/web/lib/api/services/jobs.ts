import type {
  JobDetail,
  JobOut,
  Origin,
  Track,
  TrackerStatus,
} from "@jd/shared-types";
import { api, path } from "../client";

export interface JobsFilter {
  status?: TrackerStatus | "";
  track?: Track | "";
  origin?: Origin | "";
}

export const jobsService = {
  async list(filter: JobsFilter = {}): Promise<JobOut[]> {
    const searchParams = new URLSearchParams();
    if (filter.status) searchParams.set("status", filter.status);
    if (filter.track) searchParams.set("track", filter.track);
    if (filter.origin) searchParams.set("origin", filter.origin);
    const qs = searchParams.toString();
    return api
      .get(path(`/api/jobs${qs ? `?${qs}` : ""}`))
      .json<JobOut[]>();
  },

  async detail(id: string): Promise<JobDetail> {
    return api.get(path(`/api/jobs/${id}`)).json<JobDetail>();
  },

  async track(id: string, track: Track): Promise<void> {
    await api.patch(path(`/api/jobs/${id}/track`), { json: { track } });
  },

  async generate(id: string): Promise<void> {
    await api.post(path(`/api/jobs/${id}/generate`));
  },

  async submit(id: string): Promise<void> {
    await api.post(path(`/api/jobs/${id}/submit`));
  },
};
