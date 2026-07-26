import type {
  CoverLetterTemplate,
  LatexKind,
  LatexTemplate,
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

  async listLatexTemplates(): Promise<LatexTemplate[]> {
    return api
      .get(path("/api/onboarding/latex-templates"))
      .json<LatexTemplate[]>();
  },

  async getLatexTemplate(track: Track, kind: LatexKind): Promise<LatexTemplate> {
    const sp = new URLSearchParams({ track, kind });
    return api
      .get(path(`/api/onboarding/latex-template?${sp.toString()}`))
      .json<LatexTemplate>();
  },

  async uploadLatexTemplate(
    track: Track,
    kind: LatexKind,
    file: File,
  ): Promise<LatexTemplate> {
    const form = new FormData();
    form.set("track", track);
    form.set("kind", kind);
    form.set("file", file);
    return api
      .post(path("/api/onboarding/latex-template/upload"), { body: form })
      .json<LatexTemplate>();
  },

  async setLatexTemplate(
    track: Track,
    kind: LatexKind,
    source: string,
  ): Promise<LatexTemplate> {
    return api
      .put(path("/api/onboarding/latex-template"), {
        json: { track, kind, source },
      })
      .json<LatexTemplate>();
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

  async setVerifiedExtras(
    track: Track,
    extras: Record<string, string[]>,
  ): Promise<{ track: Track; verified_extras: Record<string, string[]> }> {
    return api
      .put(path(`/api/profiles/${track}/verified-extras`), { json: { extras } })
      .json();
  },

  async setPreferences(
    track: Track,
    preferredSkills: string[],
    careerPreferences: Record<string, unknown> = {},
  ): Promise<{ track: Track; preferred_skills: string[] }> {
    return api
      .put(path(`/api/profiles/${track}/preferences`), {
        json: { preferred_skills: preferredSkills, career_preferences: careerPreferences },
      })
      .json();
  },

  async setActiveTrack(track: Track | null): Promise<{ active_track: Track | null }> {
    return api
      .put(path("/api/me/active-track"), { json: { track } })
      .json<{ active_track: Track | null }>();
  },
};
