import type {
  Origin,
  Track,
  TrackerStatus,
  WarmupStage,
} from "@jd/shared-types";

export const STATUS_LABELS: Record<TrackerStatus, string> = {
  not_applied: "Not applied",
  applied: "Applied",
  no_response: "No response",
  interviewed: "Interviewed",
  offer: "Offer",
  rejection: "Rejection",
};

/** Tailwind utility classes keyed to the status tint tokens. */
export const STATUS_TINT: Record<TrackerStatus, { dot: string; text: string }> =
  {
    not_applied: {
      dot: "bg-status-not_applied",
      text: "text-status-not_applied",
    },
    applied: { dot: "bg-status-applied", text: "text-status-applied" },
    no_response: {
      dot: "bg-status-no_response",
      text: "text-status-no_response",
    },
    interviewed: {
      dot: "bg-status-interviewed",
      text: "text-status-interviewed",
    },
    offer: { dot: "bg-status-offer", text: "text-status-offer" },
    rejection: { dot: "bg-status-rejection", text: "text-status-rejection" },
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
