"use client";

import Link from "next/link";
import type { Variant } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import styles from "./ProductCard.module.css";

const BUTTON_CLASS = `button buttonPill buttonAccentOutline ${styles.action}`;

// Every card button reads "Add to Cart" (David, 8/30 review). For
// single-variant products (26 of 32) it adds directly and opens the
// cart drawer — the drawer is the confirmation. For multi-variant
// products it deliberately does NOT add anything — silently picking a
// strength on the customer's behalf would put the wrong item in the
// cart — it links to the PDP to choose, same destination as clicking
// the product itself.
export default function ProductCardAddButton({ slug, variants }: { slug: string; variants: Variant[] }) {
  const { addItem, openDrawer } = useCart();

  if (variants.length !== 1) {
    return (
      <Link href={`/shop/${slug}`} className={BUTTON_CLASS} aria-label={`Add to cart — choose strength for ${slug}`}>
        Add to Cart
      </Link>
    );
  }

  return (
    <button
      type="button"
      className={BUTTON_CLASS}
      onClick={() => {
        addItem(variants[0].id, 1);
        openDrawer();
      }}
    >
      Add to Cart
    </button>
  );
}
