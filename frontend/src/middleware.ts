import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/signup", "/forgot-password", "/reset-password"];

/**
 * Early redirect to the login page when there is no session cookie. This is a
 * convenience only: the backend validates the session on every API request.
 */
export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname === p)) return NextResponse.next();
  if (!request.cookies.get("iios_session")) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Never intercept API calls (proxied to the backend) or static assets.
  matcher: ["/((?!api/|_next/|brand/|favicon.ico).*)"],
};
