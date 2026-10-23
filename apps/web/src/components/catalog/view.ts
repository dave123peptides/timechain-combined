// The catalog has two presentations (2026-10-22): the order sheet (one
// row per compound with the configuration, quantity and Add in the row,
// the default, built for scanning the whole offering) and the grid of
// cards (for when images matter). ?view= picks; a plain module so the
// server pages can validate it.
export type CatalogView = "list" | "grid";

export const VIEW_OPTIONS: { value: CatalogView; label: string }[] = [
  { value: "list", label: "Sheet" },
  { value: "grid", label: "Grid" },
];

export function isView(value: string | undefined): value is CatalogView {
  return VIEW_OPTIONS.some((option) => option.value === value);
}
