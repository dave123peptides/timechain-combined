import type { ProductSort } from "@/lib/api";
import { PRICING_VISIBLE } from "@/lib/site";

// Shared by the server pages (which validate ?sort=) and the client
// <ShopSort> control. A plain module on purpose: a "use client" file's
// exports cannot be called from a server component. The price sorts exist
// only while prices are shown (lib/site.ts); the API still accepts them.
const ALL_SORT_OPTIONS: { value: ProductSort; label: string }[] = [
  { value: "name", label: "Name (A to Z)" },
  { value: "price_asc", label: "Price (low to high)" },
  { value: "price_desc", label: "Price (high to low)" },
];

export const SORT_OPTIONS = PRICING_VISIBLE ? ALL_SORT_OPTIONS : ALL_SORT_OPTIONS.filter((o) => o.value === "name");

export function isSort(value: string | undefined): value is ProductSort {
  return SORT_OPTIONS.some((option) => option.value === value);
}
