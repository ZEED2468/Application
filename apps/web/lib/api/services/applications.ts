import type {
  AuditEvent,
  Paginated,
  TrackerApplication,
  TrackerStatus,
} from "@jd/shared-types";
import { api, path } from "../client";

export const applicationsService = {
  async list(page = 1, pageSize = 25): Promise<Paginated<TrackerApplication>> {
    return api
      .get(path(`/api/applications?page=${page}&page_size=${pageSize}`))
      .json<Paginated<TrackerApplication>>();
  },

  async setStatus(id: string, status: TrackerStatus): Promise<void> {
    await api.patch(path(`/api/applications/${id}/status`), {
      json: { status },
    });
  },

  async audit(id: string): Promise<AuditEvent[]> {
    return api.get(path(`/api/applications/${id}/audit`)).json<AuditEvent[]>();
  },

  /** Returns the same-origin export URL (download handled by the browser). */
  exportUrl(): string {
    return "/api/applications/export.xlsx";
  },
};
