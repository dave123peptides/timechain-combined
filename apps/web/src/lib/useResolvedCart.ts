"use client";

import { useEffect, useMemo, useState } from "react";
import { listProducts, quoteCheckout, type ProductSummary, type Quote, type Variant } from "@/lib/api";
import { useCart } from "@/lib/cart-context";

export type ResolvedCartLine = {
  variantId: string;
  quantity: number;
  // Undefined when the variant is no longer in the sellable catalog —
  // the line stays visible so the customer can remove it.
  variant?: Variant;
  productSlug?: string;
  image?: string;
  quoteLine?: Quote["items"][number];
};

// Cross-references every cart line against live product data rather than
// trusting anything cached in localStorage — a variant's price or
// availability may have changed since it was added — and prices the cart
// through the same server quote checkout uses (see
// app.constants.bulk_discounts), so bulk discounts, shipping and tax here
// always match what checkout will actually charge. Shared by the /cart
// page and the cart drawer; `enabled=false` (the drawer while closed)
// skips both requests.
export function useResolvedCart(enabled = true) {
  const { lines, hydrated } = useCart();
  const [products, setProducts] = useState<ProductSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);

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

  // Variant.images doesn't exist — images live on the parent Product —
  // so one walk of the product list resolves variant, slug and thumbnail.
  const lookup = useMemo(() => {
    const map = new Map<string, { variant: Variant; productSlug: string; image?: string }>();
    for (const product of products ?? []) {
      for (const variant of product.variants) {
        map.set(variant.id, { variant, productSlug: product.slug, image: product.images[0] });
      }
    }
    return map;
  }, [products]);

  useEffect(() => {
    if (!enabled || products === null) return;
    const items = lines
      .filter((line) => lookup.has(line.variantId))
      .map((line) => ({ variant_id: line.variantId, quantity: line.quantity }));
    if (items.length === 0) {
      setQuote(null);
      return;
    }
    let cancelled = false;
    quoteCheckout({ items })
      .then((result) => {
        if (!cancelled) {
          setQuote(result);
          setQuoteError(null);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setQuote(null);
          setQuoteError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, products, lines, lookup]);

  const quoteLineByVariantId = useMemo(() => {
    const map = new Map<string, Quote["items"][number]>();
    for (const item of quote?.items ?? []) map.set(item.variant_id, item);
    return map;
  }, [quote]);

  const resolved: ResolvedCartLine[] = lines.map((line) => ({
    ...line,
    ...lookup.get(line.variantId),
    quoteLine: quoteLineByVariantId.get(line.variantId),
  }));

  const hasUnavailable = resolved.some((line) => !line.variant);
  return {
    hydrated,
    loading: products === null && loadError === null,
    loadError,
    lines: resolved,
    quote,
    // Checkout is a money path and must fail loud; the drawer and cart
    // page may simply show "—" while this is set.
    quoteError,
    hasUnavailable,
    canCheckout: resolved.length > 0 && !hasUnavailable,
  };
}
