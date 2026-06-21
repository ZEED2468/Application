import type { AtsCheckResult } from "@jd/shared-types";
import { api, path } from "../client";

export const atsService = {
  async check(params: {
    jdText: string;
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
    if (params.cvFile) {
      form.append("file", params.cvFile);
    } else if (params.cvText?.trim()) {
      form.append("cv_text", params.cvText.trim());
    }
    return api.post(path("/api/ats/check"), { body: form }).json<AtsCheckResult>();
  },
};
