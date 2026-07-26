import type { CareerTrack } from "@jd/shared-types";
import { api, path } from "../client";

export const tracksService = {
  async list(): Promise<CareerTrack[]> {
    return api.get(path("/api/tracks")).json<CareerTrack[]>();
  },

  async create(name: string, slug?: string): Promise<CareerTrack> {
    return api
      .post(path("/api/tracks"), { json: { name, slug } })
      .json<CareerTrack>();
  },

  async rename(id: string, name: string): Promise<CareerTrack> {
    return api
      .patch(path(`/api/tracks/${id}`), { json: { name } })
      .json<CareerTrack>();
  },

  async archive(id: string): Promise<CareerTrack> {
    return api.post(path(`/api/tracks/${id}/archive`)).json<CareerTrack>();
  },

  async unarchive(id: string): Promise<CareerTrack> {
    return api.post(path(`/api/tracks/${id}/unarchive`)).json<CareerTrack>();
  },

  /** Assign an existing track's resume to this track (duplicate + edit independently). */
  async duplicateResume(id: string, sourceTrackId: string): Promise<CareerTrack> {
    return api
      .post(path(`/api/tracks/${id}/resume/from/${sourceTrackId}`))
      .json<CareerTrack>();
  },
};
