"use client";

import { useEffect, useId, useRef, type KeyboardEvent } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { formatStrength } from "@/lib/api";
import { formSingular } from "@/lib/forms";
import { useOrderRequest } from "@/lib/request-context";
import { REQUEST_PATH } from "@/lib/site";
import { useResolvedRequest } from "@/lib/useResolvedRequest";
import ProductImagePlaceholder from "@/components/ProductImagePlaceholder";
import QuantityStepper from "@/components/QuantityStepper";
import SectionIcon from "@/components/SectionIcon";
import styles from "./RequestDrawer.module.css";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

// The slide-in order request (B2B redesign, 2026-10-22), after the old
// cart drawer: opened by every Add to request and the header's Request
// button. Lines are configurations and quantities only; the summary is a
// count of lines and units, never money. Continue goes to /request, where
// contact details are added and the request is sent.
export default function RequestDrawer() {
  const { drawerOpen, closeDrawer, setQuantity, removeItem, totalQuantity } = useOrderRequest();
  const { hydrated, lines, hasUnavailable, canSubmit, loading } = useResolvedRequest(drawerOpen);
  const pathname = usePathname();
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const restoreFocusTo = useRef<HTMLElement | null>(null);

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

  // Navigating (Continue, a product link in a line) closes it.
  useEffect(() => closeDrawer(), [pathname, closeDrawer]);

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
          <div>
            <span className="eyebrow">Order request</span>
            <h2 id={titleId} className={styles.title}>
              Your request
            </h2>
          </div>
          <button ref={closeRef} type="button" className={styles.close} onClick={closeDrawer} aria-label="Close">
            <SectionIcon name="close" size={20} />
          </button>
        </header>

        <div className={styles.body}>
          {lines.length === 0 ? (
            <div className={styles.empty}>
              <p>Nothing here yet. Add compounds from the catalog with the format, strength and quantity you need.</p>
              <Link href="/shop" className="button buttonAccentOutline" onClick={closeDrawer}>
                Browse the catalog
              </Link>
            </div>
          ) : loading ? (
            <p className={styles.loading}>Checking availability…</p>
          ) : (
            <ul className={styles.lines}>
              {lines.map((line) => (
                <li key={line.variantId} className={styles.line}>
                  <div className={styles.thumb}>
                    {line.image ? (
                      // eslint-disable-next-line @next/next/no-img-element -- product images are static files under public/products
                      <img src={line.image} alt="" className={`${styles.thumbImage} productPhoto`} />
                    ) : (
                      <ProductImagePlaceholder name={line.productName ?? "?"} />
                    )}
                  </div>
                  <div className={styles.lineInfo}>
                    {line.productSlug ? (
                      <Link href={`/shop/${line.productSlug}`} className={styles.lineName}>
                        {line.productName}
                      </Link>
                    ) : (
                      <span className={styles.lineName}>Item</span>
                    )}
                    {line.variant ? (
                      <span className={styles.lineMeta}>
                        {line.variant.strength ? formatStrength(line.variant.strength) : null}
                        {line.variant.strength ? " · " : null}
                        {formSingular(line.variant.form)}
                      </span>
                    ) : (
                      <span className={styles.lineUnavailable}>No longer available. Remove to continue.</span>
                    )}
                    <div className={styles.lineControls}>
                      <QuantityStepper
                        value={line.quantity}
                        onChange={(next) => setQuantity(line.variantId, next)}
                        disabled={!line.variant}
                        label="Quantity"
                        compact
                      />
                      <button type="button" className={styles.remove} onClick={() => removeItem(line.variantId)} aria-label="Remove line">
                        <SectionIcon name="trash" size={18} />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {lines.length > 0 && (
          <div className={styles.summary}>
            <div className={styles.summaryRow}>
              <span>{lines.length === 1 ? "1 line" : `${lines.length} lines`}</span>
              <span>{totalQuantity === 1 ? "1 unit" : `${totalQuantity} units`}</span>
            </div>
            {hasUnavailable && <p className={styles.lineUnavailable}>Remove unavailable lines to continue.</p>}
            <Link
              href={REQUEST_PATH}
              className={`button buttonAccent ${styles.continue}`}
              aria-disabled={!canSubmit}
              style={{ pointerEvents: canSubmit ? "auto" : "none", opacity: canSubmit ? 1 : 0.4 }}
            >
              Continue to request
            </Link>
            <button type="button" className={`button buttonAccentOutline ${styles.keep}`} onClick={closeDrawer}>
              Keep browsing
            </button>
            <p className={styles.note}>
              No prices or payment here. We reply by email with availability, documentation and pricing for your
              quantities.
            </p>
          </div>
        )}
      </aside>
    </>
  );
}
