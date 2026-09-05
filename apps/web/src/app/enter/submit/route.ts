import { NextRequest, NextResponse } from "next/server";
import { timingSafeEqual } from "node:crypto";
import { ACCESS_COOKIE, siteAccessPassword } from "@/lib/access";

// Pre-launch lock: compare the submitted password in constant time and,
// on success, grant a session-scoped cookie (no maxAge — a fresh browser
// session has to enter the password again, which is the point while the
// site is unpublished). On failure, bounce back to the form.
export async function POST(request: NextRequest) {
  const form = await request.formData();
  const supplied = String(form.get("password") ?? "");
  const nextRaw = String(form.get("next") ?? "/");
  const next = nextRaw.startsWith("/") && !nextRaw.startsWith("//") ? nextRaw : "/";

  const expected = Buffer.from(siteAccessPassword());
  const given = Buffer.from(supplied);
  const ok = given.length === expected.length && timingSafeEqual(given, expected);

  if (!ok) {
    const url = new URL("/enter", request.url);
    url.searchParams.set("error", "1");
    url.searchParams.set("next", next);
    return NextResponse.redirect(url, 303);
  }

  const response = NextResponse.redirect(new URL(next, request.url), 303);
  response.cookies.set(ACCESS_COOKIE, "1", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });
  return response;
}
