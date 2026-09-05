import type { ProductSummary } from "@/lib/api";

// BAC water is a reconstitution supply, not a research compound, so it no
// longer appears in the catalog grids (/shop, featured, the stats count).
// It sells through the "Complete Your Protocol" block on every compound's
// PDP instead — see ReconstitutionAddon.tsx. Its own PDP stays reachable
// (cart rows and the addon card link to it), and the API still lists it:
// this is presentation-layer only, like the category removal.
export const SUPPLY_SLUGS = new Set(["bac-water"]);

export function isSupply(product: Pick<ProductSummary, "slug">): boolean {
  return SUPPLY_SLUGS.has(product.slug);
}

/** Filter for catalog surfaces that should show research compounds only. */
export function withoutSupplies<T extends Pick<ProductSummary, "slug">>(products: T[]): T[] {
  return products.filter((product) => !isSupply(product));
}
