import type {
  Origin,
  Track,
  TrackerStatus,
  WarmupStage,
} from "@jd/shared-types";

export const STATUS_LABELS: Record<TrackerStatus, string> = {
  applied: "Applied",
  interviewed: "Interviewed",
  rejected: "Rejected",
  no_response: "No response",
  accepted: "Accepted",
};

/** Tailwind utility classes keyed to the status tint tokens. */
export const STATUS_TINT: Record<TrackerStatus, { dot: string; text: string }> =
  {
    applied: { dot: "bg-status-applied", text: "text-status-applied" },
    interviewed: {
      dot: "bg-status-interviewed",
      text: "text-status-interviewed",
    },
    rejected: { dot: "bg-status-rejected", text: "text-status-rejected" },
    no_response: {
      dot: "bg-status-no_response",
      text: "text-status-no_response",
    },
    accepted: { dot: "bg-status-accepted", text: "text-status-accepted" },
  };

export const TRACK_LABELS: Record<Track, string> = {
  frontend: "Frontend",
  backend: "Backend",
  general: "General",
};

export const ORIGIN_LABELS: Record<Origin, string> = {
  auto: "Auto",
  manual: "Manual",
};

export const WARMUP_LABELS: Record<WarmupStage, string> = {
  cold: "Cold",
  warming: "Warming up",
  ready: "Ready",
  paused: "Paused",
};
