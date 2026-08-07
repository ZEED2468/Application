import type { TemplateListResponse, TemplateSummary } from "@jd/shared-types";
import { api, path } from "../client";

export const cvTemplatesService = {
  /** Built-in + custom templates for a track, plus which one is bound. */
  async list(track: string): Promise<TemplateListResponse> {
    return api
      .get(path(`/api/cv/templates?track=${encodeURIComponent(track)}`))
      .json<TemplateListResponse>();
  },

  /** Bind a template to a track (drives generation + the engine). */
  async bind(track: string, templateId: string): Promise<void> {
    await api.post(path("/api/cv/templates/bind"), {
      json: { track, template_id: templateId },
    });
  },

  /** Upload + validate a custom .tex template (rejects with reasons on the API). */
  async upload(track: string, name: string, file: File): Promise<TemplateSummary> {
    const form = new FormData();
    form.append("track", track);
    form.append("name", name);
    form.append("file", file);
    return api
      .post(path("/api/cv/templates/upload"), { body: form })
      .json<TemplateSummary>();
  },
};

export function templatePreviewPath(id: string): string {
  return `/api/cv/templates/${id}/preview`;
}
