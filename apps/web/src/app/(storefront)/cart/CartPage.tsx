"use client";

import Link from "next/link";
import { formatMoney } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { useResolvedCart } from "@/lib/useResolvedCart";
import ProductImagePlaceholder from "@/components/ProductImagePlaceholder";
import QuantityStepper from "@/components/QuantityStepper";
import styles from "./page.module.css";

// The full-page cart. Since the 9/4 redesign the slide-in drawer
// (components/cart/CartDrawer.tsx) is the primary cart; this page stays
// as the no-JS / "view full cart" fallback and shares the drawer's
// resolution + server-quote logic via useResolvedCart, so the two can
// never show different totals.
export default function CartPage() {
  const { setQuantity, removeItem } = useCart();
  const { hydrated, loading, loadError, lines, quote, hasUnavailable, canCheckout } = useResolvedCart();

  if (!hydrated || (loading && lines.length > 0)) {
    return (
      <main className="container">
        <div className={styles.head}>
          <h1>Cart</h1>
        </div>
        {loadError && <p className={styles.lineUnavailable}>{loadError}</p>}
      </main>
    );
  }

  if (lines.length === 0) {
    return (
      <main className="container">
        <div className={styles.head}>
          <h1>Cart</h1>
        </div>
        <div className={styles.empty}>
          <p>Your cart is empty.</p>
          <br />
          <Link href="/shop" className="button buttonPill buttonAccentOutline">
            Browse the Collection
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <div className={styles.head}>
        <h1>Cart</h1>
      </div>
      <div className={styles.layout}>
        <div className={styles.lines}>
          {lines.map((line) => {
            const bulkSavingsPercent =
              line.quoteLine && line.variant && line.quoteLine.unit_price_cents < (line.variant.price_cents ?? 0)
                ? Math.round((1 - line.quoteLine.unit_price_cents / (line.variant.price_cents ?? 0)) * 100)
                : 0;
            return (
              <div key={line.variantId} className={styles.line}>
                <div className={styles.lineImageWrap}>
                  {line.image ? (
                    // eslint-disable-next-line @next/next/no-img-element -- product images are arbitrary external URLs from Product.images
                    <img src={line.image} alt="" className={styles.lineImage} />
                  ) : (
                    <ProductImagePlaceholder name={line.variant?.name ?? "?"} />
                  )}
                </div>
                <div>
                  <div className={styles.lineName}>{line.variant?.name ?? "Item"}</div>
                  {line.variant ? (
                    <div className={styles.lineMeta}>
                      {formatMoney(line.quoteLine?.unit_price_cents ?? (line.variant.price_cents ?? 0))} each
                      {bulkSavingsPercent > 0 && <span className={styles.bulkBadge}> Save {bulkSavingsPercent}%</span>}
                    </div>
                  ) : (
                    <div className={styles.lineUnavailable}>No longer available — remove to continue.</div>
                  )}
                  <button type="button" className={styles.removeButton} onClick={() => removeItem(line.variantId)}>
                    Remove
                  </button>
                </div>
                <QuantityStepper
                  value={line.quantity}
                  onChange={(next) => setQuantity(line.variantId, next)}
                  disabled={!line.variant}
                  label="Quantity"
                  compact
                />
                <span className={styles.lineTotal}>
                  {line.quoteLine ? formatMoney(line.quoteLine.total_price_cents) : line.variant ? "…" : "—"}
                </span>
              </div>
            );
          })}
        </div>

        <div className={styles.summary}>
          <div className={styles.summaryRow}>
            <span>Subtotal</span>
            <span>{quote ? formatMoney(quote.subtotal_cents) : "…"}</span>
          </div>
          <div className={styles.summaryRow}>
            <span>Shipping</span>
            <span>{quote ? formatMoney(quote.shipping_cents) : "Calculated at checkout"}</span>
          </div>
          <div className={styles.summaryRow}>
            <span>Tax</span>
            <span>{quote ? formatMoney(quote.tax_cents) : "…"}</span>
          </div>
          <div className={styles.summaryTotal}>
            <span>Total</span>
            <span>{quote ? formatMoney(quote.total_cents) : "…"}</span>
          </div>
          {hasUnavailable && <p className={styles.lineUnavailable}>Remove unavailable items to proceed.</p>}
          <Link
            href="/checkout"
            className="button buttonPill buttonAccent"
            style={{ width: "100%", pointerEvents: canCheckout ? "auto" : "none", opacity: canCheckout ? 1 : 0.4 }}
          >
            Checkout
          </Link>
          <p className={styles.note}>For laboratory research use only.</p>
        </div>
      </div>
    </main>
  );
}
