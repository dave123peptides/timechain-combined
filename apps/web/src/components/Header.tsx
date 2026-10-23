"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart-context";
import { useOrderRequest } from "@/lib/request-context";
import { ORDERING_ENABLED } from "@/lib/site";
import SectionIcon from "@/components/SectionIcon";
import HeaderSearch from "./HeaderSearch";
import styles from "./Header.module.css";

// B2B redesign (David, 2026-10-22, after the OT and American Peptides
// references): a thin ticker of facts above a floating pill bar. The bar
// holds the wordmark, the primary pages, search, and the one action on
// the site: the order request list. Every fact in the ticker is one this
// codebase or David stands behind (see FAQ copy and SELLABLE_FORMS);
// nothing about purity, shipping or speed.
const TICKER = [
  "Compounded, tested and verified in the United States",
  "Pre-filled pens and lyophilized vials",
  "Certificates of Analysis on request",
  "For laboratory research use only",
];

const NAV = [
  { href: "/shop", label: "Catalog" },
  { href: "/shop?form=pen", label: "Pens" },
  { href: "/shop?form=lyophilized", label: "Vials" },
  { href: "/coa", label: "Quality" },
  { href: "/contact", label: "Contact" },
];

function isActive(pathname: string, href: string): boolean {
  // The two format links share /shop; only the plain Catalog link lights
  // up there (the toggle on the page shows the active format).
  if (href.includes("?")) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Header() {
  const { totalQuantity: cartQuantity, hydrated: cartHydrated, openDrawer: openCart } = useCart();
  const { lineCount, hydrated, openDrawer } = useOrderRequest();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => setMenuOpen(false), [pathname]);

  const links = NAV.map((item) => (
    <Link
      key={item.href}
      href={item.href}
      className={`${styles.navLink} ${isActive(pathname, item.href) ? styles.navLinkActive : ""}`}
      aria-current={isActive(pathname, item.href) ? "page" : undefined}
    >
      {item.label}
    </Link>
  ));

  return (
    <>
      <div className={styles.ticker} aria-label="About our products">
        <ul className={styles.tickerList}>
          {TICKER.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      </div>

      <header className={styles.header}>
        <div className={`container ${styles.barWrap}`}>
          <div className={styles.bar}>
            <Link href="/" className={styles.wordmark}>
              TimeChain
              <span className={styles.wordmarkSuffix}>Peptides</span>
            </Link>

            <nav className={styles.nav} aria-label="Primary">
              {links}
            </nav>

            <div className={styles.tools}>
              <HeaderSearch />
              {ORDERING_ENABLED && (
                <button type="button" className={styles.iconButton} onClick={openCart} aria-label="Open cart">
                  <SectionIcon name="bag" size={20} />
                  {cartHydrated && cartQuantity > 0 && <span className={styles.count}>{cartQuantity}</span>}
                </button>
              )}
              <button type="button" className={styles.requestButton} onClick={openDrawer} aria-label="Open your order request">
                <SectionIcon name="layers" size={18} />
                <span className={styles.requestLabel}>Request</span>
                {hydrated && lineCount > 0 && <span className={styles.count}>{lineCount}</span>}
              </button>
              <button
                type="button"
                className={styles.menuToggle}
                aria-label={menuOpen ? "Close menu" : "Open menu"}
                aria-expanded={menuOpen}
                aria-controls="primary-mobile-nav"
                onClick={() => setMenuOpen((open) => !open)}
              >
                <SectionIcon name={menuOpen ? "close" : "menu"} size={22} />
              </button>
            </div>
          </div>

          <nav
            id="primary-mobile-nav"
            className={`${styles.mobileNav} ${menuOpen ? styles.mobileNavOpen : ""}`}
            aria-label="Primary (mobile)"
            hidden={!menuOpen}
          >
            {links}
          </nav>
        </div>
      </header>
    </>
  );
}
