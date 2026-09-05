import { NextRequest, NextResponse } from "next/server";
import { AGE_ACK_COOKIE } from "@/middleware";

const MAX_AGE_SECONDS = 60 * 60 * 24 * 180; // ~180 days

// Records the site-entry age self-attestation as a real
// httpOnly/secure/sameSite cookie. This used to be a Server Action, but
// production builds of Next 15.5 fail to resolve MPA-submitted actions
// ("Failed to find Server Action" → 500; dev mode worked), so the gate
// now POSTs here instead — a plain form POST to a route handler is
// equivalent and immune to that bug. This records that the
// self-attestation checkbox was checked; it is not, and must never be
// described as, identity verification.
export async function POST(request: NextRequest) {
  const form = await request.formData();
  const next = (form.get("next") as string | null) || "/";
  // Open-redirect guard: only internal paths, never //host or absolute URLs.
  const safeNext = next.startsWith("/") && !next.startsWith("//") ? next : "/";

  const response = NextResponse.redirect(new URL(safeNext, request.url), 303);
  response.cookies.set(AGE_ACK_COOKIE, "1", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
  return response;
}
