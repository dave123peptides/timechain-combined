"use client";

import { useState } from "react";
import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { formatStrength } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { STOREFRONT_FORMS, formSingular, formsIn, type FormKey } from "@/lib/forms";
import { useOrderRequest } from "@/lib/request-context";
import { ORDERING_ENABLED } from "@/lib/site";
import ProductImagePlaceholder from "@/components/ProductImagePlaceholder";
import styles from "./CatalogRow.module.css";

const DEFAULT_QUANTITY = 10;

// Pens first, then vials, strengths ascending within each: the order a
// practice reads a configuration list in, rather than the API's price
// order.
function sortConfigurations(variants: ProductSummary["variants"]): ProductSummary["variants"] {
  const rank = (form: string | null) => STOREFRONT_FORMS.findIndex((f) => f.key === form);
  const leading = (strength: string | null) => Number.parseFloat(strength ?? "") || 0;
  return [...variants].sort((a, b) => rank(a.form) - rank(b.form) || leading(a.strength) - leading(b.strength));
}

// One row of the order sheet (2026-10-22): the compound, its formats,
// and the three controls a practice needs to order it without leaving
// the list: which configuration, how many, Add. The configuration list
// is the product's sellable variants labelled "10mg · Pen"; a product
// with one configuration shows it as text. The name and thumbnail still
// open the product page for the full copy and certificates.
export default function CatalogRow({ product, form }: { product: ProductSummary; form?: FormKey }) {
  const { addItem: addToCart, openDrawer: openCart } = useCart();
  const { addItem, openDrawer } = useOrderRequest();
  const options = sortConfigurations(product.variants);
  const initial = (form ? options.find((v) => v.form === form) : undefined) ?? options[0];
  const [variantId, setVariantId] = useState(initial?.id ?? "");
  const [quantity, setQuantity] = useState(DEFAULT_QUANTITY);
  const [added, setAdded] = useState(false);

  const href = `/shop/${product.slug}${form ? `?form=${form}` : ""}`;
  const image = product.images[0];
  const forms = formsIn(product.variants);
  const label = (variant: ProductSummary["variants"][number]) =>
    `${variant.strength ? formatStrength(variant.strength) : variant.format} · ${formSingular(variant.form)}`;

  const add = () => {
    if (!variantId) return;
    const qty = Math.max(1, Math.floor(quantity) || 1);
    if (ORDERING_ENABLED) {
      addToCart(variantId, qty);
      openCart();
      return;
    }
    addItem(variantId, qty);
    setAdded(true);
    openDrawer();
    window.setTimeout(() => setAdded(false), 1800);
  };

  return (
    <li className={styles.row}>
      <Link href={href} className={styles.thumb} aria-label={product.name}>
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element -- static product files
          <img src={image} alt="" className={`${styles.thumbImage} productPhoto`} loading="lazy" decoding="async" />
        ) : (
          <ProductImagePlaceholder name={product.name} />
        )}
      </Link>

      <div className={styles.identity}>
        <Link href={href} className={styles.name}>
          {product.name}
        </Link>
        {product.description && <span className={styles.subtitle}>{product.description}</span>}
      </div>

      <div className={styles.formats} aria-label="Formats">
        {forms.map((f) => (
          <span key={f.key} className={styles.badge}>
            {f.singular}
          </span>
        ))}
      </div>

      <div className={styles.controls}>
        {product.variants.length > 1 ? (
          <select className={styles.select} value={variantId} onChange={(e) => setVariantId(e.target.value)} aria-label={`Configuration for ${product.name}`}>
            {options.map((variant) => (
              <option key={variant.id} value={variant.id}>
                {label(variant)}
              </option>
            ))}
          </select>
        ) : (
          <span className={styles.single}>{initial ? label(initial) : "—"}</span>
        )}
        <input
          type="number"
          min={1}
          className={styles.quantity}
          value={quantity}
          onChange={(e) => setQuantity(Number(e.target.value))}
          aria-label={`Quantity of ${product.name}`}
        />
        <button type="button" className={`${styles.add} ${added ? styles.addDone : ""}`} onClick={add}>
          {ORDERING_ENABLED ? "Add to cart" : added ? "Added" : "Add"}
        </button>
      </div>
    </li>
  );
}
