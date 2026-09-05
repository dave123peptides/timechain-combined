import type { ProductSort } from "@/lib/api";

// Shared by the server pages (which validate ?sort=) and the client
// <ShopSort> control. A plain module on purpose: a "use client" file's
// exports cannot be called from a server component.
export const SORT_OPTIONS: { value: ProductSort; label: string }[] = [
  { value: "name", label: "Name (A–Z)" },
  { value: "price_asc", label: "Price (low to high)" },
  { value: "price_desc", label: "Price (high to low)" },
];

export function isSort(value: string | undefined): value is ProductSort {
  return SORT_OPTIONS.some((option) => option.value === value);
}
