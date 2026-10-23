"use client";

import { useEffect, useMemo, useState } from "react";
import { listProducts, type ProductSummary, type Variant } from "@/lib/api";
import { useOrderRequest } from "@/lib/request-context";

export type ResolvedRequestLine = {
  variantId: string;
  quantity: number;
  // Undefined when the variant is no longer in the sellable catalog; the
  // line stays visible so it can be removed.
  variant?: Variant;
  productSlug?: string;
  productName?: string;
  image?: string;
};

// Cross-references every request line against the live catalog rather
// than trusting anything cached in localStorage (a configuration may have
// been withdrawn since it was added). No quote: there are no prices on
// this site. Shared by the drawer and the /request page; `enabled=false`
// (the drawer while closed) skips the fetch.
export function useResolvedRequest(enabled = true) {
  const { lines, hydrated } = useOrderRequest();
  const [products, setProducts] = useState<ProductSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !hydrated || products !== null) return;
    let cancelled = false;
    listProducts()
      .then((found) => {
        if (!cancelled) setProducts(found);
      })
      .catch((err: Error) => {
        if (!cancelled) setLoadError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, hydrated, products]);

  const lookup = useMemo(() => {
    const map = new Map<string, { variant: Variant; productSlug: string; productName: string; image?: string }>();
    for (const product of products ?? []) {
      for (const variant of product.variants) {
        map.set(variant.id, { variant, productSlug: product.slug, productName: product.name, image: product.images[0] });
      }
    }
    return map;
  }, [products]);

  const resolved: ResolvedRequestLine[] = lines.map((line) => ({ ...line, ...lookup.get(line.variantId) }));
  const hasUnavailable = products !== null && resolved.some((line) => !line.variant);

  return {
    hydrated,
    loading: products === null && loadError === null,
    loadError,
    lines: resolved,
    hasUnavailable,
    canSubmit: products !== null && resolved.length > 0 && !hasUnavailable,
  };
}
