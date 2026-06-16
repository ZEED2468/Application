import type {
  DomainHealth,
  DomainsResponse,
  HunterQuota,
  QuotaResponse,
} from "@jd/shared-types";
import { api, path } from "../client";

export const adminService = {
  async domains(): Promise<DomainHealth[]> {
    const res = await api
      .get(path("/api/admin/domains"))
      .json<DomainsResponse | DomainHealth[]>();
    return Array.isArray(res) ? res : res.domains;
  },

  async quota(): Promise<HunterQuota[]> {
    const res = await api
      .get(path("/api/admin/quota"))
      .json<QuotaResponse | HunterQuota[]>();
    return Array.isArray(res) ? res : res.hunters;
  },
};
