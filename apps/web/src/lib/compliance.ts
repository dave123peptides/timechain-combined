import type { ProductSummary } from "@/lib/api";

// GLP-class compounds. These are sellable and findable, but must never be
// PROMOTED.
//
// Background: an April 2026 FDA warning-letter batch hit three vendors
// using this same code-name scheme, and the letters cited consumer-demand
// signalling — featured placement, "best seller" framing, outcome claims —
// as evidence of intended drug use. David's decision is the survivor
// pattern: keep them purchasable, strip the marketing-voice mechanism
// language (see seed_pen_catalog.py), and give them no promotional
// surface at all.
//
// EXCLUDE them from: the hero spotlight, featured/"popular" sections, any
// badge, and any curated suggestion list.
//
// Do NOT exclude them from: /shop listings, category filtering, the search
// results (direct lookup by name is deliberate — someone who already knows
// what they want should find it), pairs_with cross-links between GLP
// products, or the /coa document index.
//
// TCP pens site (David, 2026-09-05): the slugs stay code names so this
// filter keeps working, but the DISPLAY names carry the drug name in
// parentheses — "GLP-3R (Retatrutide)" — set in
// services/api/app/scripts/seed_pen_catalog.py. That departs from the
// vial site's never-print-drug-names rule. TODO(attorney-review).
export const UNPROMOTED_SLUGS = new Set(["glp-1s", "glp-2t", "glp-3r", "cagrilinitide"]);

export function isPromotable(product: Pick<ProductSummary, "slug">): boolean {
  return !UNPROMOTED_SLUGS.has(product.slug);
}

/** Filter for any surface that promotes rather than merely lists products. */
export function promotableOnly<T extends Pick<ProductSummary, "slug">>(products: T[]): T[] {
  return products.filter(isPromotable);
}
