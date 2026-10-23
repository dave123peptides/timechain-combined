// Site-wide facts and switches for the combined storefront: pens and
// lyophilized vials at timechainpeptides.com (David, 2026-10-22).
export const SITE_NAME = "TimeChain Peptides";
export const SUPPORT_EMAIL = "support@timechainpeptides.com";

// David (2026-10-22): the site takes no payments. Visitors browse the
// catalog and book a meeting from /contact; orders are arranged
// directly. Off unless the build sets NEXT_PUBLIC_ORDERING_ENABLED=true,
// which restores the cart, the checkout and the Add to Cart buttons. The
// API has the matching switch (ORDERING_ENABLED) that refuses checkout
// writes outright, so flipping only this one shows a checkout that
// cannot complete.
export const ORDERING_ENABLED = process.env.NEXT_PUBLIC_ORDERING_ENABLED === "true";

// Booking a meeting is the site's ONLY action (David, 2026-10-23: "the
// only CTA I want is book a meeting and it goes straight to the calendar
// link"). Every Book a meeting button is a plain link to BOOKING_URL, the
// Cal.com page David supplies, opened in a new tab. Until it is set the
// buttons fall back to email so nothing dead-ends.
export const BOOKING_URL = process.env.NEXT_PUBLIC_BOOKING_URL?.trim() || null;
export const BOOKING_HREF = BOOKING_URL ?? `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("Meeting request")}`;
// Link attributes for the booking button: a new tab for the calendar, the
// mail app for the fallback.
export const BOOKING_TARGET: { target?: string; rel?: string } = BOOKING_URL ? { target: "_blank", rel: "noopener noreferrer" } : {};

export const CONTACT_PATH = "/contact";

// Redesign (David, 2026-10-22): no prices on the site until the wholesale
// sheet exists. The API has the matching switch (CATALOG_PRICES_PUBLIC)
// that nulls the price fields, so flipping only this one shows nothing.
export const PRICING_VISIBLE = process.env.NEXT_PUBLIC_PRICING_VISIBLE === "true";

// Who the site is for, in David's words (2026-10-22). TODO(attorney-review):
// "medical practices" alongside the research-use-only language.
export const AUDIENCE = "research organizations and medical practices";

// /contact?product=<slug>&variant=<id>: the page names what the visitor
// was looking at so the conversation can start from it.
export function contactHref(productSlug?: string, variantId?: string): string {
  const params = new URLSearchParams();
  if (productSlug) params.set("product", productSlug);
  if (variantId) params.set("variant", variantId);
  const qs = params.toString();
  return qs ? `${CONTACT_PATH}?${qs}` : CONTACT_PATH;
}
