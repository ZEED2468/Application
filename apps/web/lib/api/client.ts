import ky, { HTTPError, type KyInstance } from "ky";

/**
 * Same-origin API client. All calls hit `/api/...` which is the catch-all
 * proxy route handler that forwards to FastAPI (carrying httpOnly cookies).
 *
 * On a 401, attempt `/api/auth/refresh` once. If refresh fails, redirect to
 * login (browser only).
 */

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  if (!refreshing) {
    refreshing = ky
      .post("/api/auth/refresh", { throwHttpErrors: false })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        // allow a fresh attempt next cycle
        setTimeout(() => {
          refreshing = null;
        }, 0);
      });
  }
  return refreshing;
}

function redirectToLogin() {
  if (typeof window === "undefined") return;
  const next = encodeURIComponent(
    window.location.pathname + window.location.search,
  );
  window.location.href = `/login?next=${next}`;
}

export const api: KyInstance = ky.create({
  prefixUrl: typeof window === "undefined" ? undefined : "/api",
  // When running on the server (RSC), use an absolute path via the proxy is
  // not available; client components are the primary consumers.
  retry: 0,
  hooks: {
    afterResponse: [
      async (request, _options, response) => {
        if (response.status !== 401) return response;
        // don't try to refresh the refresh/login endpoints themselves
        if (
          request.url.includes("/auth/refresh") ||
          request.url.includes("/auth/login")
        ) {
          return response;
        }
        const ok = await tryRefresh();
        if (!ok) {
          redirectToLogin();
          return response;
        }
        // replay original request once
        return ky(request);
      },
    ],
  },
});

export interface ApiError {
  status: number;
  message: string;
  detail?: unknown;
}

export async function toApiError(err: unknown): Promise<ApiError> {
  if (err instanceof HTTPError) {
    let detail: unknown;
    let message = err.message;
    try {
      const body = (await err.response.clone().json()) as {
        detail?: unknown;
        message?: string;
      };
      detail = body?.detail;
      if (typeof body?.detail === "string") message = body.detail;
      else if (typeof body?.message === "string") message = body.message;
    } catch {
      // non-JSON body
    }
    return { status: err.response.status, message, detail };
  }
  return { status: 0, message: (err as Error)?.message ?? "Network error" };
}

/**
 * Make a path relative for ky's `prefixUrl: "/api"`. Services pass absolute
 * `/api/...` strings for readability; ky would otherwise double the prefix
 * (`/api/api/...`), so strip the leading `/api/` segment here.
 */
export function path(p: string): string {
  return p.replace(/^\/?api\/?/, "");
}
