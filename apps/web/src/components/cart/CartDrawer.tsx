"use client";

import { useEffect, useId, useRef, type KeyboardEvent } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { formatMoney } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { useResolvedCart } from "@/lib/useResolvedCart";
import ProductImagePlaceholder from "@/components/ProductImagePlaceholder";
import QuantityStepper from "@/components/QuantityStepper";
import SectionIcon from "@/components/SectionIcon";
import styles from "./CartDrawer.module.css";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

// The slide-in cart (Core reference, 9/4). Rendered from the storefront
// layout as a sibling of the header — it must NOT live inside Header,
// whose sticky positioning creates a stacking context nothing inside it
// can escape (see globals.css; --z-drawer-scrim / --z-drawer are
// reserved for exactly this). Opened by every Add to Cart and the header
// cart button (cart-context's drawerOpen). Totals come from the same
// server quote as /cart and checkout, fetched only once the drawer opens.
export default function CartDrawer() {
  const { drawerOpen, closeDrawer, setQuantity, removeItem } = useCart();
  const { hydrated, lines, quote, hasUnavailable, canCheckout, loading } = useResolvedCart(drawerOpen);
  const pathname = usePathname();
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const restoreFocusTo = useRef<HTMLElement | null>(null);

  // Focus in on open, back to the opener on close; lock the page behind.
  useEffect(() => {
    if (!drawerOpen) return;
    restoreFocusTo.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      restoreFocusTo.current?.focus?.();
    };
  }, [drawerOpen]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") closeDrawer();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen, closeDrawer]);

  // Navigating (the Checkout link, a product link in a line) closes it.
  useEffect(() => closeDrawer(), [pathname, closeDrawer]);

  // Keep Tab inside the panel while it is open.
  const trapTab = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Tab" || !panelRef.current) return;
    const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!hydrated) return null;

  const subtotal = quote?.subtotal_cents;

  return (
    <>
      <div className={`${styles.scrim} ${drawerOpen ? styles.scrimOpen : ""}`} onClick={closeDrawer} aria-hidden="true" />
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`${styles.panel} ${drawerOpen ? styles.panelOpen : ""}`}
        inert={!drawerOpen}
        onKeyDown={trapTab}
      >
        <header className={styles.head}>
          <button ref={closeRef} type="button" className={styles.back} onClick={closeDrawer} aria-label="Close cart">
            <SectionIcon name="chevronLeft" size={22} />
          </button>
          <h2 id={titleId} className={styles.title}>
            Your Cart
          </h2>
        </header>

        <div className={styles.body}>
          {lines.length === 0 ? (
            <p className={styles.empty}>Your cart is empty.</p>
          ) : loading ? (
            <p className={styles.empty}>Loading your cart…</p>
          ) : (
            <ul className={styles.lines}>
              {lines.map((line) => (
                <li key={line.variantId} className={styles.line}>
                  <div className={styles.thumb}>
                    {line.image ? (
                      // eslint-disable-next-line @next/next/no-img-element -- product images are arbitrary URLs from Product.images
                      <img src={line.image} alt="" className={styles.thumbImage} />
                    ) : (
                      <ProductImagePlaceholder name={line.variant?.name ?? "?"} />
                    )}
                  </div>
                  <div className={styles.lineInfo}>
                    {line.productSlug ? (
                      <Link href={`/shop/${line.productSlug}`} className={styles.lineName}>
                        {line.variant?.name}
                      </Link>
                    ) : (
                      <span className={styles.lineName}>Item</span>
                    )}
                    {line.variant ? (
                      <span className={styles.linePrice}>
                        {formatMoney(line.quoteLine?.total_price_cents ?? line.variant.price_cents * line.quantity)}
                      </span>
                    ) : (
                      <span className={styles.lineUnavailable}>No longer available — remove to continue.</span>
                    )}
                    <div className={styles.lineControls}>
                      <QuantityStepper
                        value={line.quantity}
                        onChange={(next) => setQuantity(line.variantId, next)}
                        disabled={!line.variant}
                        label="Quantity"
                        compact
                      />
                      <button type="button" className={styles.remove} onClick={() => removeItem(line.variantId)} aria-label="Remove item">
                        <SectionIcon name="trash" size={18} />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className={styles.summary}>
          <div className={styles.summaryRow}>
            <span>Subtotal</span>
            <span>{subtotal !== undefined ? formatMoney(subtotal) : "—"}</span>
          </div>
          <div className={styles.summaryRow}>
            <span>Shipping</span>
            <span>{quote ? formatMoney(quote.shipping_cents) : "Calculated at checkout"}</span>
          </div>
          <div className={styles.summaryRow}>
            <span>Tax</span>
            <span>{quote ? formatMoney(quote.tax_cents) : "—"}</span>
          </div>
          <div className={styles.summaryTotal}>
            <span>Total</span>
            <span>{quote ? `${formatMoney(quote.total_cents)} USD` : "—"}</span>
          </div>
          {hasUnavailable && <p className={styles.lineUnavailable}>Remove unavailable items to proceed.</p>}
          <Link
            href="/checkout"
            className={`button buttonPill buttonAccent ${styles.checkout}`}
            aria-disabled={!canCheckout}
            style={{ pointerEvents: canCheckout ? "auto" : "none", opacity: canCheckout ? 1 : 0.4 }}
          >
            Checkout
          </Link>
          <button type="button" className={`button buttonPill buttonPrimary ${styles.returnButton}`} onClick={closeDrawer}>
            Return to Store
          </button>
          <Link href="/cart" className={styles.fullCart}>
            View full cart
          </Link>
          <p className={styles.note}>For laboratory research use only.</p>
        </div>
      </aside>
    </>
  );
}
