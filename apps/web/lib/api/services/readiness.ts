import type { UserReadiness } from "@jd/shared-types";
import { api, path } from "../client";

export const readinessService = {
  /** The single source of truth for onboarding/setup progress. */
  async get(): Promise<UserReadiness> {
    return api.get(path("/api/user/readiness")).json<UserReadiness>();
  },
};
