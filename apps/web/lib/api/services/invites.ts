import type {
  AdminInviteRequest,
  HunterInviteRequest,
  InviteCreatedResponse,
  InviteOut,
  VaInviteRequest,
} from "@jd/shared-types";
import { api, path } from "../client";

export const invitesService = {
  async list(): Promise<InviteOut[]> {
    return api.get(path("/api/invites")).json<InviteOut[]>();
  },

  async inviteHunter(
    body: HunterInviteRequest,
  ): Promise<InviteCreatedResponse> {
    return api
      .post(path("/api/invites/hunter"), { json: body })
      .json<InviteCreatedResponse>();
  },

  async inviteAdmin(body: AdminInviteRequest): Promise<InviteCreatedResponse> {
    return api
      .post(path("/api/invites/admin"), { json: body })
      .json<InviteCreatedResponse>();
  },

  async inviteVa(body: VaInviteRequest): Promise<InviteCreatedResponse> {
    return api
      .post(path("/api/invites/va"), { json: body })
      .json<InviteCreatedResponse>();
  },

  async revoke(id: string): Promise<void> {
    await api.delete(path(`/api/invites/${id}`), { throwHttpErrors: false });
  },
};
