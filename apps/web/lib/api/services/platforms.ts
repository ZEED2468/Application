import type {
  AdminOut,
  Platform,
  PlatformCreate,
  SourceBoard,
  SourceBoardCreate,
} from "@jd/shared-types";
import { api, path } from "../client";

export const platformsService = {
  async list(): Promise<Platform[]> {
    return api.get(path("/api/platforms")).json<Platform[]>();
  },

  async create(body: PlatformCreate): Promise<Platform> {
    return api.post(path("/api/platforms"), { json: body }).json<Platform>();
  },

  async setActive(id: string, is_active: boolean): Promise<Platform> {
    return api
      .patch(path(`/api/platforms/${id}`), { json: { is_active } })
      .json<Platform>();
  },

  async listAdmins(): Promise<AdminOut[]> {
    return api.get(path("/api/admins")).json<AdminOut[]>();
  },
};

export const sourceBoardsService = {
  async list(): Promise<SourceBoard[]> {
    return api.get(path("/api/source-boards")).json<SourceBoard[]>();
  },

  async create(body: SourceBoardCreate): Promise<SourceBoard> {
    return api.post(path("/api/source-boards"), { json: body }).json<SourceBoard>();
  },

  async setActive(id: string, is_active: boolean): Promise<SourceBoard> {
    return api
      .patch(path(`/api/source-boards/${id}`), { json: { is_active } })
      .json<SourceBoard>();
  },
};
