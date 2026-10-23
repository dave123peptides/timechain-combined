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

// The meeting-booking page David will supply (a hosted scheduling form).
// Until it is set, /contact offers email instead.
export const BOOKING_URL = process.env.NEXT_PUBLIC_BOOKING_URL?.trim() || null;

export const CONTACT_PATH = "/contact";

// /contact?product=<slug>&variant=<id>: the page names what the visitor
// was looking at so the conversation can start from it.
export function contactHref(productSlug?: string, variantId?: string): string {
  const params = new URLSearchParams();
  if (productSlug) params.set("product", productSlug);
  if (variantId) params.set("variant", variantId);
  const qs = params.toString();
  return qs ? `${CONTACT_PATH}?${qs}` : CONTACT_PATH;
}
