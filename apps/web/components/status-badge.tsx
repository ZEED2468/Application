import type { TrackerStatus } from "@jd/shared-types";
import { cn } from "@/lib/utils";
import { STATUS_LABELS, STATUS_TINT } from "@/lib/status";

export function StatusBadge({
  status,
  className,
}: {
  status: TrackerStatus;
  className?: string;
}) {
  const tint = STATUS_TINT[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-coffee-300 bg-white px-2.5 py-0.5 text-xs font-medium",
        className,
      )}
    >
      <span className={cn("size-2 rounded-full", tint.dot)} />
      <span className="text-coffee-700">{STATUS_LABELS[status]}</span>
    </span>
  );
}
