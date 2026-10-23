import type { ProductSummary, Variant } from "@/lib/api";

// The two forms this storefront sells (David, 2026-10-22: the union of
// the pens site and the vial site). Mirrors SELLABLE_FORMS in
// services/api/app/models/catalog.py. The API's FORM_LABEL gives the
// bare label ("Pen", "Lyophilized"); this file gives the words the
// storefront uses for each line.
export type FormKey = "pen" | "lyophilized";

export type StorefrontForm = {
  key: FormKey;
  // Plural, for the Pens | Vials toggle and page titles.
  label: string;
  // Singular, for the format picker on a product page.
  singular: string;
  // The spec-list "Form" row.
  shipsAs: string;
  // The banner line and the grid's standing note.
  description: string;
};

export const STOREFRONT_FORMS: StorefrontForm[] = [
  {
    key: "pen",
    label: "Pens",
    singular: "Pen",
    shipsAs: "Pre-filled 3 mL auto-injector pen",
    description: "Pre-filled 3 mL auto-injector pens. Ready to use, no reconstitution.",
  },
  {
    key: "lyophilized",
    label: "Vials",
    singular: "Vial",
    shipsAs: "Lyophilized powder in a sealed vial",
    description: "Lyophilized (freeze-dried) powder in sealed vials. Reconstitute before use.",
  },
];

export function findForm(key: string | null | undefined): StorefrontForm | undefined {
  return STOREFRONT_FORMS.find((form) => form.key === key);
}

/** Validates a ?form= query value; anything unknown means "all". */
export function isFormKey(value: string | null | undefined): value is FormKey {
  return findForm(value) !== undefined;
}

/** The forms a variant list actually contains, in STOREFRONT_FORMS order. */
export function formsIn(variants: Pick<Variant, "form">[]): StorefrontForm[] {
  return STOREFRONT_FORMS.filter((form) => variants.some((variant) => variant.form === form.key));
}

/**
 * The catalog as one line sees it: products with at least one variant of
 * `form`, each carrying only those variants, with the "From" price
 * recomputed over them. Same result as the API's ?format= filter
 * (storefront.list_sellable_products), done here so a single fetch
 * serves both the grid and the toggle's counts.
 */
export function narrowToForm(products: ProductSummary[], form: StorefrontForm): ProductSummary[] {
  return products.flatMap((product) => {
    const variants = product.variants.filter((variant) => variant.form === form.key);
    if (variants.length === 0) return [];
    const prices = variants.map((v) => v.price_cents).filter((p): p is number => p !== null);
    return [{ ...product, variants, starting_price_cents: prices.length ? Math.min(...prices) : null }];
  });
}

/** "Pen" / "Vial" for a raw form key, falling back to the key itself. */
export function formSingular(form: string | null | undefined): string {
  return findForm(form)?.singular ?? form ?? "";
}

/**
 * Distinct strengths of a variant list, ascending by their leading number
 * ("1.5", "10", "10/10/50", "10mL"), so a compound sold as pens and vials
 * reads "1.5mg, 3.5mg, 10mg" rather than in the API's per-form order.
 */
export function strengthList(variants: Pick<Variant, "strength">[]): string[] {
  const seen = new Set<string>();
  for (const variant of variants) {
    if (variant.strength) seen.add(variant.strength);
  }
  const leading = (strength: string) => Number.parseFloat(strength) || 0;
  return [...seen].sort((a, b) => leading(a) - leading(b) || a.localeCompare(b));
}
