import { NextRequest, NextResponse } from "next/server";

/**
 * Gate the (authed) route group. Anything that is not /login, not /api/*, and
 * not a static asset requires an `access_token` cookie; otherwise redirect to
 * /login?next=<original>.
 */

const PUBLIC_PATHS = ["/login"];

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;

  // allow public paths and the proxy/auth endpoints through
  if (
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`)) ||
    pathname.startsWith("/api")
  ) {
    return NextResponse.next();
  }

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
