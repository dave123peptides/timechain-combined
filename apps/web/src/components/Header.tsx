"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart-context";
import { ORDERING_ENABLED } from "@/lib/site";
import SectionIcon from "@/components/SectionIcon";
import HeaderSearch from "./HeaderSearch";
import styles from "./Header.module.css";

// Core-reference header (9/4): light bar, wordmark left, the primary
// pages centered as uppercase links, search pill and the main action on
// the right. No account icon: there are no customer accounts. No
// category links here; the format toggle and category pills sit above
// the catalog grid. No COAs link (David, 9/5): certificates belong to
// each product and are reached from the product page; /coa still exists
// via the footer. Contact is back (David, 2026-10-22): booking a meeting
// is how this site is used, so it gets a nav link and, in place of the
// cart button, a pill. The cart button returns with ordering
// (lib/site.ts).
const NAV = [
  { href: "/", label: "Home" },
  { href: "/shop", label: "Shop" },
  { href: "/contact", label: "Contact" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Header() {
  const { totalQuantity, hydrated, openDrawer } = useCart();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  // The mobile menu is a navigation aid, not a page: any route change
  // closes it, including the one its own links cause.
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
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <Link href="/" className={styles.wordmark}>
          Time<span>Chain</span>
          <span className={styles.wordmarkSuffix}> Peptides</span>
        </Link>

        <nav className={styles.nav} aria-label="Primary">
          {links}
        </nav>

        <div className={styles.tools}>
          <HeaderSearch />
          {ORDERING_ENABLED ? (
            // Opens the cart drawer (rendered from the storefront layout;
            // it cannot live inside this sticky header, see globals.css).
            // The footer keeps a plain /cart link for no-JS and for anyone
            // who prefers the full page.
            <button type="button" className={styles.cartButton} onClick={openDrawer} aria-label="Open cart">
              <SectionIcon name="bag" size={22} />
              {hydrated && totalQuantity > 0 && <span className={styles.cartCount}>{totalQuantity}</span>}
            </button>
          ) : (
            <Link href="/contact" className={`button buttonPill buttonAccent ${styles.contactButton}`}>
              Contact us
            </Link>
          )}
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

      {/* The same links, stacked, for viewports where the centered row
          doesn't fit. Anchored to the bottom of the bar like the mobile
          search field, so --header-h stays accurate while it is open. */}
      <nav
        id="primary-mobile-nav"
        className={`${styles.mobileNav} ${menuOpen ? styles.mobileNavOpen : ""}`}
        aria-label="Primary (mobile)"
        hidden={!menuOpen}
      >
        {links}
      </nav>
    </header>
  );
}
