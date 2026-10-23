// The catalog has two presentations (2026-10-23): cards grouped by
// category (the default: built to see the different peptides at a glance,
// one button per card) and the order sheet (one dense row per compound
// with the configuration, quantity and Add in the row). ?view= picks; a
// plain module so the server pages can validate it.
export type CatalogView = "cards" | "sheet";

export const VIEW_OPTIONS: { value: CatalogView; label: string }[] = [
  { value: "cards", label: "Cards" },
  { value: "sheet", label: "Sheet" },
];

export const DEFAULT_VIEW: CatalogView = "cards";

export function isView(value: string | undefined): value is CatalogView {
  return VIEW_OPTIONS.some((option) => option.value === value);
}
