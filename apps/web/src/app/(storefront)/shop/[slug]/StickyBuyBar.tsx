"use client";

import { useEffect, useState, type RefObject } from "react";
import { formatMoney } from "@/lib/api";
import QuantityStepper from "@/components/QuantityStepper";
import styles from "./page.module.css";

const DESKTOP_QUERY = "(min-width: 781px)";

// Why this isn't just `position: sticky` on the buy box: the PDP grid is
// `1fr 1fr` with `align-items: start`. The gallery column sticks only
// because the RIGHT column is the taller one and therefore defines the row
// height. Sticking an element inside the right column does nothing — its
// containing block is only as tall as itself — and nothing inside the grid
// can stay pinned across ProductTabs / RelatedProducts /
// ProductFaq, which are siblings after the grid.
//
// So the existing mobile fixed bar is promoted to a shared component. On
// mobile it behaves exactly as before (always visible). On desktop it
// slides up once the real Add to Cart button has scrolled out of view.
export default function StickyBuyBar({
  watchRef,
  priceCents,
  quantity,
  onQuantityChange,
  onAdd,
}: {
  watchRef: RefObject<HTMLElement | null>;
  priceCents: number;
  quantity: number;
  onQuantityChange: (next: number) => void;
  onAdd: () => void;
}) {
  // Starts true so mobile — where the bar is always on — renders correctly
  // before the effect runs and never flashes.
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const desktop = window.matchMedia(DESKTOP_QUERY);
    const target = watchRef.current;
    let observer: IntersectionObserver | undefined;

    const apply = () => {
      observer?.disconnect();
      if (!desktop.matches) {
        // Mobile: unchanged behaviour, no observer needed.
        setVisible(true);
        return;
      }
      if (!target) return;
      // Desktop starts hidden — the initial `true` above exists for mobile,
      // and without this the bar flashes on for one frame before the
      // observer's first callback arrives.
      setVisible(false);
      observer = new IntersectionObserver(
        ([entry]) => {
          // Only once the button has scrolled UP out of view — not merely
          // because it is still below the fold. Without the direction
          // check the bar is on at scroll-top, duplicating a buy box the
          // customer can already see and covering content for no reason.
          const scrolledPast = entry.boundingClientRect.top < 0;
          setVisible(!entry.isIntersecting && scrolledPast);
        },
        // Accounts for the sticky header, so the bar
        // appears as the button disappears behind them rather than when
        // it crosses the literal viewport edge.
        { rootMargin: "-140px 0px 0px 0px" }
      );
      observer.observe(target);
    };

    apply();
    desktop.addEventListener("change", apply);
    return () => {
      desktop.removeEventListener("change", apply);
      observer?.disconnect();
    };
  }, [watchRef]);

  return (
    <div className={`${styles.buyBar} ${visible ? styles.buyBarVisible : ""}`}>
      <span className={styles.buyBarPrice}>{formatMoney(priceCents)}</span>
      <div className={styles.buyBarActions}>
        <QuantityStepper value={quantity} onChange={onQuantityChange} compact label="Quantity" />
        <button type="button" className="button buttonPill buttonAccent" onClick={onAdd}>
          Add to Cart
        </button>
      </div>
    </div>
  );
}
