import type { Paginated, VaItemKind, VaQueueItem } from "@jd/shared-types";
import { api, path } from "../client";

/** Backend may return a flat list or the legacy grouped object — normalize both. */
const LEGACY_KIND: Record<string, VaItemKind> = {
  to_submit: "submit",
  submit: "submit",
  outreach_review: "outreach_review",
  replies: "reply",
  reply: "reply",
};

function normalizeQueue(data: unknown): VaQueueItem[] {
  if (Array.isArray(data)) {
    return data as VaQueueItem[];
  }
  if (data && typeof data === "object") {
    const grouped = data as Record<string, unknown[]>;
    const out: VaQueueItem[] = [];
    for (const [rawKind, rows] of Object.entries(grouped)) {
      if (!Array.isArray(rows)) continue;
      const kind = LEGACY_KIND[rawKind] ?? (rawKind as VaItemKind);
      for (const row of rows) {
        if (!row || typeof row !== "object") continue;
        const r = row as Record<string, unknown>;
        out.push({
          id: String(r.outreach_id ?? r.dossier_id ?? r.job_id ?? crypto.randomUUID()),
          kind,
          job_id: String(r.job_id ?? ""),
          company: String(r.company ?? ""),
          role: String(r.role ?? ""),
          hunter_name: String(r.hunter_name ?? ""),
          track: (r.track as VaQueueItem["track"]) ?? "general",
          preview: (r.preview ?? r.subject ?? r.summary ?? null) as string | null,
          created_at: String(r.created_at ?? new Date().toISOString()),
        });
      }
    }
    return out;
  }
  return [];
}

export const vaService = {
  async queue(page = 1, pageSize = 25): Promise<Paginated<VaQueueItem>> {
    const raw = await api
      .get(path(`/api/va/queue?page=${page}&page_size=${pageSize}`))
      .json<unknown>();
    if (raw && typeof raw === "object" && "items" in (raw as object)) {
      const p = raw as {
        items: unknown;
        total?: number;
        page?: number;
        page_size?: number;
      };
      const items = normalizeQueue(p.items);
      return {
        items,
        total: p.total ?? items.length,
        page: p.page ?? page,
        page_size: p.page_size ?? pageSize,
      };
    }
    const items = normalizeQueue(raw);
    return { items, total: items.length, page: 1, page_size: items.length || pageSize };
  },
};
