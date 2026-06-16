import type { AuditEvent, TrackerStatus } from "@jd/shared-types";
import { api, path } from "../client";

export const applicationsService = {
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
