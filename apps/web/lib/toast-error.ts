import { toast } from "sonner";
import { toApiError } from "@/lib/api/client";

/**
 * Show a standardized, actionable error toast from any API error.
 * Surfaces the backend `title` + `message` + a clickable `action` (e.g. the
 * feature-guard "Upload Resume" → route) when present.
 */
export async function toastApiError(err: unknown, fallback = "Something went wrong"): Promise<void> {
  const e = await toApiError(err);
  const heading = e.title || e.message || fallback;
  const description = e.title ? e.message : e.remediation;
  const action = e.action
    ? {
        label: e.action.label,
        onClick: () => {
          window.location.href = e.action!.route;
        },
      }
    : undefined;
  toast.error(heading, { description, action });
}
