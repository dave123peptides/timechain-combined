// Pre-launch site lock. While a password is configured, every new browser
// session must pass /enter before anything else (including the age gate)
// is reachable. The password lives in SITE_ACCESS_PASSWORD; the hardcoded
// value is the pre-launch default (David, 2026-09-05) so the lock is never
// accidentally absent. Replace this module with the email-code login when
// that is built; remove it at public launch.
export const ACCESS_COOKIE = "tcp_access"; // not the vial site's tc_access: cookies ignore ports on localhost

export function siteAccessPassword(): string {
  return process.env.SITE_ACCESS_PASSWORD ?? "health123";
}

// The cookie carries a token derived from the password, not a bare "1",
// so it cannot be forged by anyone who merely knows the cookie name, and
// changing the password signs every existing session out. SHA-256 via
// Web Crypto so the same code runs in the edge middleware and in the
// Node route handler.
let cachedToken: { password: string; token: string } | undefined;

export async function accessToken(): Promise<string> {
  const password = siteAccessPassword();
  if (cachedToken?.password === password) return cachedToken.token;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`tcp-access-v1:${password}`));
  const token = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  cachedToken = { password, token };
  return token;
}

export async function hasValidAccessToken(cookieValue: string | undefined): Promise<boolean> {
  return cookieValue !== undefined && cookieValue === (await accessToken());
}
