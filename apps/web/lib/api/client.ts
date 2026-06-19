import ky, { HTTPError, type KyInstance } from "ky";

/**
 * Browser API client — mode switches on NODE_ENV:
 *
 *  - production:  call the FastAPI backend DIRECTLY at NEXT_PUBLIC_API_BASE
 *    (e.g. https://jd-be.quickbiteltd.org). The backend must allow this origin
 *    via CORS_ORIGINS and set cross-site cookies (SameSite=None;Secure if the
 *    frontend is a different site). Falls back to the same-origin proxy if
 *    NEXT_PUBLIC_API_BASE is not set.
 *  - development: always use the same-origin `/api/[...path]` proxy → the local
 *    backend (no CORS, no cross-site cookies, no env var needed).
 *
 * Either way, `credentials: "include"` sends the httpOnly auth cookie.
 */

const IS_PROD = process.env.NODE_ENV === "production";
// Inlined at build time by Next; only used in production.
const PUBLIC_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

/** "" = same-origin proxy; otherwise the backend origin (prod + configured). */
const API_ROOT = IS_PROD && PUBLIC_BASE ? PUBLIC_BASE : "";

/** Base for ky. */
const PREFIX_URL =
  typeof window === "undefined" ? undefined : `${API_ROOT}/api`;

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  if (!refreshing) {
    refreshing = ky
      .post(`${API_ROOT}/api/auth/refresh`, {
        credentials: "include",
        throwHttpErrors: false,
        timeout: 30000,
      })
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
  prefixUrl: PREFIX_URL,
  // Send the httpOnly auth cookie on cross-origin requests.
  credentials: "include",
  // 30s (ky default is 10s) — login runs argon2 + may hit a cold backend start.
  timeout: 30000,
  // Client components are the primary consumers (RSC uses server fetches).
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
