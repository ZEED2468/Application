import type {
  ApplyResult,
  DiscoverReport,
  JobDetail,
  JobOut,
  Origin,
  Paginated,
  Track,
  TrackerStatus,
} from "@jd/shared-types";
import { api, path } from "../client";

export interface JobsFilter {
  status?: TrackerStatus | "";
  track?: Track | "";
  origin?: Origin | "";
}

/** Backend returns a flat job row; normalize to the nested JobDetail shape. */
function normalizeJobDetail(raw: Record<string, unknown>): JobDetail {
  const {
    cv,
    cover_letter: coverLetter,
    application,
    outreach,
    thread,
    description,
    ...jobFields
  } = raw;

  const job: JobDetail["job"] = {
    ...(jobFields as unknown as JobOut),
    description: (description as string | null) ?? null,
    jd_text: (description as string | null) ?? null,
  };

  const app = application as Record<string, unknown> | null | undefined;
  const outreachList = (outreach as Record<string, unknown>[] | undefined) ?? [];

  return {
    job,
    generated_cv: (cv as unknown as JobDetail["generated_cv"]) ?? null,
    cover_letter:
      (coverLetter as unknown as JobDetail["cover_letter"]) ?? null,
    application: app
      ? {
          id: String(app.id),
          status:
            (app.application_status as TrackerStatus) ??
            (app.tracker_status as TrackerStatus) ??
            "applied",
          submitted_at: (app.submitted_at as string | null) ?? null,
        }
      : null,
    outreach:
      outreachList.length > 0
        ? (outreachList[0] as unknown as JobDetail["outreach"])
        : null,
    thread: (thread as unknown as JobDetail["thread"]) ?? [],
  };
}

export const jobsService = {
  async list(
    filter: JobsFilter = {},
    page = 1,
    pageSize = 25,
  ): Promise<Paginated<JobOut>> {
    const searchParams = new URLSearchParams();
    if (filter.status) searchParams.set("status", filter.status);
    if (filter.track) searchParams.set("track", filter.track);
    if (filter.origin) searchParams.set("origin", filter.origin);
    searchParams.set("page", String(page));
    searchParams.set("page_size", String(pageSize));
    return api
      .get(path(`/api/jobs?${searchParams.toString()}`))
      .json<Paginated<JobOut>>();
  },

  async discover(): Promise<DiscoverReport> {
    // 60s: discovery makes live HTTP calls to each source.
    return api
      .post(path("/api/jobs/discover"), { timeout: 60000 })
      .json<DiscoverReport>();
  },

  async detail(id: string): Promise<JobDetail> {
    const raw = await api.get(path(`/api/jobs/${id}`)).json<Record<string, unknown>>();
    return normalizeJobDetail(raw);
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

  /** VA's final action: record the application + get the apply link + docs to attach. */
  async apply(id: string): Promise<ApplyResult> {
    return api.post(path(`/api/jobs/${id}/apply`)).json<ApplyResult>();
  },

  async setApplicationStatus(
    id: string,
    status: TrackerStatus,
  ): Promise<JobOut> {
    return api
      .patch(path(`/api/jobs/${id}/application-status`), { json: { status } })
      .json<JobOut>();
  },
};
