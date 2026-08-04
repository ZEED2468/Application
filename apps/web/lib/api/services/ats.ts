import type {
  AtsCheckResult,
  AtsLatestAnalysis,
  AtsSources,
  RegenerateAtsRecs,
  Track,
} from "@jd/shared-types";
import { api, path } from "../client";

export const atsService = {
  async sources(): Promise<AtsSources> {
    return api.get(path("/api/ats/sources")).json<AtsSources>();
  },

  async suggestTrack(params: {
    jdText: string;
    roleTitle?: string;
  }): Promise<{ track: Track; method: string; reason: string }> {
    return api
      .post(path("/api/ats/suggest-track"), {
        json: {
          jd_text: params.jdText,
          role_title: params.roleTitle || undefined,
        },
      })
      .json();
  },

  async check(params: {
    jdText: string;
    track?: Track | null;
    cvText?: string;
    cvFile?: File | null;
    roleTitle?: string;
    useAi?: boolean;
    jobId?: string | null;
  }): Promise<AtsCheckResult> {
    const form = new FormData();
    form.append("jd_text", params.jdText);
    form.append("use_ai", String(params.useAi !== false));
    if (params.roleTitle?.trim()) {
      form.append("role_title", params.roleTitle.trim());
    }
    if (params.track) {
      form.append("track", params.track);
    }
    // Bind the check to a job so its analysis persists against it (server-side).
    if (params.jobId) {
      form.append("job_id", params.jobId);
    }
    if (params.cvFile) {
      form.append("file", params.cvFile);
    } else if (params.cvText?.trim()) {
      form.append("cv_text", params.cvText.trim());
    }
    return api.post(path("/api/ats/check"), { body: form }).json<AtsCheckResult>();
  },

  /** The latest persisted ATS recommendations for a job (or the standalone check). */
  async latestRecs(jobId?: string | null): Promise<RegenerateAtsRecs | null> {
    const qs = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
    const res = await api
      .get(path(`/api/ats/analysis${qs}`))
      .json<AtsLatestAnalysis | null>();
    return res?.recs ?? null;
  },
};
