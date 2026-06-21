import { NextRequest } from "next/server";
import { BACKEND_URL } from "@/lib/env";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
/** Allow Render cold starts (requires Vercel Pro for >10s on some plans). */
export const maxDuration = 60;

/**
 * Catch-all proxy: browser → /api/<path>  ⇒  FastAPI <BACKEND_URL>/api/<path>.
 * Forwards cookies in both directions so the httpOnly access/refresh cookies
 * set by FastAPI on the login/refresh flow travel through to the browser.
 */

const UPSTREAM_TIMEOUT_MS = 55_000;

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "content-length",
  "host",
]);

async function handle(req: NextRequest, segments: string[]): Promise<Response> {
  if (!BACKEND_URL) {
    return new Response(
      JSON.stringify({
        detail:
          "BACKEND_URL is not configured. Set it in the hosting env " +
          "(e.g. Vercel → Settings → Environment Variables) to your FastAPI URL.",
      }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  const search = req.nextUrl.search;
  const target = `${BACKEND_URL}/api/${segments.map(encodeURIComponent).join("/")}${search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });
  // ensure the backend sees the originating host as the proxy
  headers.set("x-forwarded-host", req.headers.get("host") ?? "");

  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";

  const init: RequestInit & { duplex?: "half" } = {
    method,
    headers,
    redirect: "manual",
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  };

  if (hasBody) {
    const contentType = req.headers.get("content-type") ?? "";
    // JSON and small bodies: buffer explicitly (duplex streaming is flaky on Vercel).
    if (contentType.includes("multipart/form-data")) {
      init.body = req.body;
      init.duplex = "half";
    } else {
      init.body = await req.arrayBuffer();
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (err) {
    const reason =
      err instanceof Error && err.name === "TimeoutError"
        ? "Backend timed out (Render may be waking up — wait a minute and retry)."
        : "Could not connect to the API server.";
    return new Response(
      JSON.stringify({
        detail: "Upstream backend unavailable.",
        hint: `${reason} On Vercel, set BACKEND_URL to your Render API URL (e.g. https://application-yye1.onrender.com) and redeploy.`,
      }),
      {
        status: 502,
        headers: { "content-type": "application/json" },
      },
    );
  }

  // Build response, forwarding Set-Cookie and other headers.
  const resHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP.has(lower)) return;
    if (lower === "set-cookie") return; // handled below
    // fetch() already decompressed the body, so the upstream content-encoding /
    // content-length no longer describe what we're streaming. Forwarding them
    // makes the browser try to decode an already-decoded body → "content
    // decoding failed". Drop them and let the platform re-set them.
    if (lower === "content-encoding" || lower === "content-length") return;
    resHeaders.set(key, value);
  });

  // Next's Headers may collapse multiple Set-Cookie; use getSetCookie when available.
  const setCookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : [];
  for (const cookie of setCookies) {
    resHeaders.append("set-cookie", cookie);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: resHeaders,
  });
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return handle(req, path);
}
export async function POST(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return handle(req, path);
}
export async function PATCH(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return handle(req, path);
}
export async function PUT(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return handle(req, path);
}
export async function DELETE(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return handle(req, path);
}
