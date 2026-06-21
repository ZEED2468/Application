import type { AtsCheckResult, AtsSources, Track } from "@jd/shared-types";
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
    if (params.cvFile) {
      form.append("file", params.cvFile);
    } else if (params.cvText?.trim()) {
      form.append("cv_text", params.cvText.trim());
    }
    return api.post(path("/api/ats/check"), { body: form }).json<AtsCheckResult>();
  },
};
