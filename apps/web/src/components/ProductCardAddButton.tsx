"use client";

import Link from "next/link";
import type { Variant } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { ORDERING_ENABLED, contactHref } from "@/lib/site";
import styles from "./ProductCard.module.css";

const BUTTON_CLASS = `button buttonPill buttonAccentOutline ${styles.action}`;

// Inquiry mode (David, 2026-10-22, the default): there is no cart, so
// every card's button opens the contact page pre-filled with the
// product.
//
// With ordering on, every card button reads "Add to Cart" (David, 8/30
// review). For single-variant products it adds directly and opens the
// cart drawer, which is the confirmation. For multi-variant products it
// deliberately does NOT add anything (silently picking a strength on the
// customer's behalf would put the wrong item in the cart); it links to
// the PDP to choose, same destination as clicking the product itself.
export default function ProductCardAddButton({ slug, variants, href }: { slug: string; variants: Variant[]; href: string }) {
  const { addItem, openDrawer } = useCart();

  if (!ORDERING_ENABLED) {
    return (
      <Link href={contactHref(slug)} className={BUTTON_CLASS} aria-label={`Contact us about ${slug}`}>
        Contact us
      </Link>
    );
  }

  if (variants.length !== 1) {
    return (
      <Link href={href} className={BUTTON_CLASS} aria-label={`Add to cart — choose strength for ${slug}`}>
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
