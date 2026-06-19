/**
 * Server-side environment access. Never import this in client components.
 *
 * BACKEND_URL is the FastAPI base URL the `/api/[...path]` proxy forwards to.
 * It is the single source of truth for backend communication and must be set in
 * the hosting env (e.g. Vercel → Settings → Environment Variables):
 *   BACKEND_URL=https://jd-be.quickbiteltd.org
 * In development it defaults to http://localhost:8000; in production it is
 * REQUIRED — if missing, the proxy returns a clear 500 instead of silently
 * hitting localhost (which would 502 on a serverless host).
 */
export const BACKEND_URL =
  process.env.BACKEND_URL?.replace(/\/$/, "") ||
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

  