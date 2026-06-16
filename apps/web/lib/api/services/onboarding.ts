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

  async setCoverLetterTemplate(body: string): Promise<CoverLetterTemplate> {
    return api
      .put(path("/api/onboarding/cover-letter-template"), { json: { body } })
      .json<CoverLetterTemplate>();
  },

  async confirm(track: Track): Promise<void> {
    await api.post(path(`/api/profiles/${track}/confirm`));
  },
};
