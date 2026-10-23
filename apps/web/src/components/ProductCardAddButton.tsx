"use client";

import Link from "next/link";
import type { Variant } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { useOrderRequest } from "@/lib/request-context";
import { ORDERING_ENABLED } from "@/lib/site";
import styles from "./ProductCard.module.css";

const BUTTON_CLASS = `button buttonAccentOutline ${styles.action}`;

// Every card button builds the order request (B2B redesign, 2026-10-22).
// A single-configuration product adds one unit and opens the drawer,
// where the quantity is set; a product with several formats or strengths
// links to its page to choose, same destination as clicking the product.
// With ordering on (lib/site.ts) the old Add to Cart behaviour returns.
export default function ProductCardAddButton({ slug, variants, href }: { slug: string; variants: Variant[]; href: string }) {
  const { addItem: addToCart, openDrawer: openCart } = useCart();
  const { addItem, openDrawer } = useOrderRequest();

  if (variants.length !== 1) {
    return (
      <Link href={href} className={BUTTON_CLASS} aria-label={`Choose a format and strength for ${slug}`}>
        Choose options
      </Link>
    );
  }

  if (ORDERING_ENABLED) {
    return (
      <button
        type="button"
        className={BUTTON_CLASS}
        onClick={() => {
          addToCart(variants[0].id, 1);
          openCart();
        }}
      >
        Add to Cart
      </button>
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
      Add to request
    </button>
  );
}
