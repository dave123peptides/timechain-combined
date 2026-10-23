"use client";

import { useState } from "react";
import type { ProductSummary, Variant } from "@/lib/api";
import { formatStrength } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { STOREFRONT_FORMS, formSingular, type FormKey } from "@/lib/forms";
import { useOrderRequest } from "@/lib/request-context";
import { ORDERING_ENABLED } from "@/lib/site";
import styles from "./ProductCard.module.css";

const DEFAULT_QUANTITY = 10;

// Pens first, then vials, strengths ascending within each.
function sortConfigurations(variants: Variant[]): Variant[] {
  const rank = (form: string | null) => STOREFRONT_FORMS.findIndex((f) => f.key === form);
  const leading = (strength: string | null) => Number.parseFloat(strength ?? "") || 0;
  return [...variants].sort((a, b) => rank(a.form) - rank(b.form) || leading(a.strength) - leading(b.strength));
}

function label(variant: Variant): string {
  return `${variant.strength ? formatStrength(variant.strength) : variant.format} · ${formSingular(variant.form)}`;
}

// One button per card (2026-10-23, David: the sheet was "too much of what
// do I do"). A single-configuration product adds straight to the request
// (quantity is edited in the drawer). A product with several formats or
// strengths opens a small panel on the card to pick one and a quantity,
// then adds. With ordering on (lib/site.ts) the same panel feeds the cart.
export default function ProductCardActions({ product, form }: { product: ProductSummary; form?: FormKey }) {
  const { addItem: addToCart, openDrawer: openCart } = useCart();
  const { addItem, openDrawer } = useOrderRequest();
  const options = sortConfigurations(product.variants);
  const initial = (form ? options.find((v) => v.form === form) : undefined) ?? options[0];
  const [open, setOpen] = useState(false);
  const [variantId, setVariantId] = useState(initial?.id ?? "");
  const [quantity, setQuantity] = useState(DEFAULT_QUANTITY);
  const [added, setAdded] = useState(false);

  const commit = (id: string, qty: number) => {
    const safe = Math.max(1, Math.floor(qty) || 1);
    if (ORDERING_ENABLED) {
      addToCart(id, safe);
      openCart();
      return;
    }
    addItem(id, safe);
    setAdded(true);
    setOpen(false);
    openDrawer();
    window.setTimeout(() => setAdded(false), 1800);
  };

  if (options.length <= 1) {
    return (
      <button type="button" className={`button buttonAccentOutline ${styles.action}`} onClick={() => initial && commit(initial.id, DEFAULT_QUANTITY)}>
        {ORDERING_ENABLED ? "Add to cart" : added ? "Added" : "Add to request"}
      </button>
    );
  }

  if (!open) {
    return (
      <button type="button" className={`button buttonAccentOutline ${styles.action}`} onClick={() => setOpen(true)} aria-expanded={false}>
        {added ? "Added" : ORDERING_ENABLED ? "Add to cart" : "Add to request"}
      </button>
    );
  }

  return (
    <div className={styles.chooser} role="group" aria-label={`Choose a configuration for ${product.name}`}>
      <select className={styles.chooserSelect} value={variantId} onChange={(e) => setVariantId(e.target.value)} aria-label="Configuration">
        {options.map((variant) => (
          <option key={variant.id} value={variant.id}>
            {label(variant)}
          </option>
        ))}
      </select>
      <div className={styles.chooserRow}>
        <input
          type="number"
          min={1}
          className={styles.chooserQuantity}
          value={quantity}
          onChange={(e) => setQuantity(Number(e.target.value))}
          aria-label="Quantity"
        />
        <button type="button" className={`button buttonAccent ${styles.chooserAdd}`} onClick={() => variantId && commit(variantId, quantity)}>
          Add
        </button>
        <button type="button" className={styles.chooserCancel} onClick={() => setOpen(false)} aria-label="Cancel">
          Cancel
        </button>
      </div>
    </div>
  );
}
