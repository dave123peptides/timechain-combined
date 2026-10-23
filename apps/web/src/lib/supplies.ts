import type { ProductSummary } from "@/lib/api";

// BAC water is a reconstitution supply, not a research compound (ported
// from the vial site, 2026-10-22). It is listed in the catalog like any
// product (there is no cart to attach it to), but it belongs to no
// benefit group (lib/categories.ts), is never promoted, and its product
// page describes a diluent rather than a lyophilized compound
// (FormatNotice, VariantPicker's Form row).
export const BAC_WATER_SLUG = "bac-water";
export const SUPPLY_SLUGS = new Set([BAC_WATER_SLUG]);

export function isSupply(product: Pick<ProductSummary, "slug"> | string): boolean {
  return SUPPLY_SLUGS.has(typeof product === "string" ? product : product.slug);
}
