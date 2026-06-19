import { NextRequest, NextResponse } from "next/server";

/**
 * Gate the (authed) route group.
 *
 * In PROXY mode (same-origin) the auth cookie lives on THIS domain, so we gate on
 * it here. In DIRECT mode (NEXT_PUBLIC_API_BASE set → the browser calls the
 * backend cross-origin) the cookie lives on the backend domain and is invisible
 * here, so we can't gate server-side — the client-side AuthGuard does it instead.
 */

const PUBLIC_PATHS = ["/login", "/signup"];
const DIRECT_MODE = Boolean(process.env.NEXT_PUBLIC_API_BASE);

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;

  // allow public paths and the proxy/auth endpoints through
  if (
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`)) ||
    pathname.startsWith("/api")
  ) {
    return NextResponse.next();
  }

  // Direct mode: the cookie isn't visible here; let AuthGuard handle it.
  if (DIRECT_MODE) return NextResponse.next();

  const hasToken = Boolean(req.cookies.get("access_token")?.value);
  if (hasToken) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(pathname + search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  // run on everything except Next internals and obvious static files
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
