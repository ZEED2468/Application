import type { VaQueueItem } from "@jd/shared-types";
import { api, path } from "../client";

export const vaService = {
  async queue(): Promise<VaQueueItem[]> {
    return api.get(path("/api/va/queue")).json<VaQueueItem[]>();
  },
};
