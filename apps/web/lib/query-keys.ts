import type { JobsFilter } from "./api/services";

export const queryKeys = {
  me: ["me"] as const,
  profiles: ["profiles"] as const,
  jobs: (filter: JobsFilter = {}) => ["jobs", filter] as const,
  job: (id: string) => ["job", id] as const,
  audit: (applicationId: string) => ["audit", applicationId] as const,
  chatSession: (id: string) => ["chat-session", id] as const,
  vaQueue: ["va-queue"] as const,
  domains: ["domains"] as const,
  quota: ["quota"] as const,
  invites: ["invites"] as const,
};
