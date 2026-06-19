import { NextRequest } from "next/server";
import { BACKEND_URL } from "@/lib/env";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Catch-all proxy: browser → /api/<path>  ⇒  FastAPI <BACKEND_URL>/api/<path>.
 * Forwards cookies in both directions so the httpOnly access/refresh cookies
 * set by FastAPI on the login/refresh flow travel through to the browser.
 * Handles GET/POST/PATCH/PUT/DELETE and multipart bodies (we stream the raw
 * body and copy content-type, so FormData/file uploads pass through).
 */

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
  };

  if (hasBody) {
    // stream the raw body (works for JSON and multipart alike)
    init.body = req.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return new Response(
      JSON.stringify({
        detail: "Upstream backend unavailable.",
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
