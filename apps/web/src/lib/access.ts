// Pre-launch site lock. While a password is configured, every new browser
// session must pass /enter before anything else (including the age gate)
// is reachable. The password lives in SITE_ACCESS_PASSWORD; the hardcoded
// value is only the pre-launch default so the lock is never accidentally
// absent. Remove this module (and its middleware/route references) at
// public launch.
export const ACCESS_COOKIE = "tcp_access"; // not the vial site's tc_access: cookies ignore ports on localhost

export function siteAccessPassword(): string {
  return process.env.SITE_ACCESS_PASSWORD ?? "Verified 2026";
}
