import { NextResponse, type NextRequest } from "next/server";
import { ACCESS_COOKIE, hasValidAccessToken } from "@/lib/access";

// Site-entry age self-attestation — a plain "I confirm I am 21+"
// checkbox-equivalent, deliberately not framed as identity verification
// anywhere. See app/age-gate/. This cookie only gates entry to the site;
// checkout requires its own, separate acknowledgment regardless of it.
export const AGE_ACK_COOKIE = "tcp_age_ack";

function unauthorized() {
  return new NextResponse("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="admin"' },
  });
}

// Defense-in-depth only — the real boundary is FastAPI's own
// require_admin_auth dependency (app/core/admin_auth.py), since the
// admin page's browser JS calls the API directly, cross-origin. This
// just stops the admin bundle itself from loading for a casual visitor.
// Same env vars/values as the API's admin_basic_auth_user/password —
// server-only, never NEXT_PUBLIC_*.
function isAdminAuthorized(request: NextRequest): boolean {
  const user = process.env.ADMIN_BASIC_AUTH_USER;
  const password = process.env.ADMIN_BASIC_AUTH_PASSWORD;
  if (!user || !password) {
    return false;
  }

  const header = request.headers.get("authorization");
  if (!header?.startsWith("Basic ")) {
    return false;
  }

  const decoded = atob(header.slice("Basic ".length));
  const separatorIndex = decoded.indexOf(":");
  if (separatorIndex === -1) {
    return false;
  }
  const suppliedUser = decoded.slice(0, separatorIndex);
  const suppliedPassword = decoded.slice(separatorIndex + 1);
  return suppliedUser === user && suppliedPassword === password;
}

export async function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/admin")) {
    return isAdminAuthorized(request) ? NextResponse.next() : unauthorized();
  }

  // Pre-launch lock: everything (including the age gate) sits behind the
  // access password until the cookie proves this session passed /enter
  // (its value is verified, not just its presence — see lib/access.ts).
  if (!(await hasValidAccessToken(request.cookies.get(ACCESS_COOKIE)?.value))) {
    const url = request.nextUrl.clone();
    url.pathname = "/enter";
    url.search = "";
    url.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search);
    return NextResponse.redirect(url);
  }

  if (request.cookies.has(AGE_ACK_COOKIE)) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/age-gate";
  url.search = "";
  url.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    // Everything except: the gate itself (avoid a redirect loop), Next
    // internals, and any file with an extension (static assets). /admin
    // is included (handled separately above with Basic Auth instead of
    // the age-gate) since it now needs its own auth check.
    "/((?!enter|age-gate|_next/static|_next/image|favicon.ico|.*\\..*).*)",
  ],
};
