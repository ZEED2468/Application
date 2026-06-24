import type {
  CoverLetterTemplate,
  MasterProfile,
  RoleCv,
  Track,
} from "@jd/shared-types";
import { api, path } from "../client";

export const onboardingService = {
  async profiles(): Promise<MasterProfile[]> {
    return api.get(path("/api/profiles")).json<MasterProfile[]>();
  },

  async uploadRoleCv(track: Track, file: File): Promise<RoleCv> {
    const form = new FormData();
    form.set("track", track);
    form.set("file", file);
    return api
      .post(path("/api/onboarding/role-cv"), { body: form })
      .json<RoleCv>();
  },

  async getCoverLetterTemplate(): Promise<CoverLetterTemplate> {
    return api
      .get(path("/api/onboarding/cover-letter-template"))
      .json<CoverLetterTemplate>();
  },

  async uploadCoverLetterTemplate(file: File): Promise<CoverLetterTemplate> {
    const form = new FormData();
    form.set("file", file);
    return api
      .post(path("/api/onboarding/cover-letter-template/upload"), { body: form })
      .json<CoverLetterTemplate>();
  },

  async setCoverLetterTemplate(body: string): Promise<CoverLetterTemplate> {
    return api
      .put(path("/api/onboarding/cover-letter-template"), { json: { body } })
      .json<CoverLetterTemplate>();
  },

  async confirm(track: Track): Promise<void> {
    await api.post(path(`/api/profiles/${track}/confirm`));
  },

  async setTargetRoles(
    track: Track,
    roles: string[],
  ): Promise<{ track: Track; target_roles: string[] }> {
    return api
      .put(path(`/api/profiles/${track}/target-roles`), { json: { roles } })
      .json<{ track: Track; target_roles: string[] }>();
  },
};
