/**
 * Server-side environment access. Never import this in client components.
 */
export const BACKEND_URL =
  process.env.BACKEND_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
