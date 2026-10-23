"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart-context";
import { BOOKING_HREF, BOOKING_TARGET, ORDERING_ENABLED } from "@/lib/site";
import SectionIcon from "@/components/SectionIcon";
import HeaderSearch from "./HeaderSearch";
import styles from "./Header.module.css";

// A flat white bar (modern, minimal, 2026-10-22): wordmark, the primary
// pages, search, and the one action on the site, Book a meeting, a plain
// link to the calendar (David, 2026-10-23).
const NAV = [
  { href: "/shop", label: "Catalog" },
  { href: "/shop?form=pen", label: "Pens" },
  { href: "/shop?form=lyophilized", label: "Vials" },
  { href: "/coa", label: "Quality" },
  { href: "/contact", label: "Contact" },
];

function isActive(pathname: string, href: string): boolean {
  if (href.includes("?")) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Header() {
  const { totalQuantity: cartQuantity, hydrated: cartHydrated, openDrawer: openCart } = useCart();
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
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <Link href="/" className={styles.wordmark}>
          <span className={styles.mark} aria-hidden="true" />
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
          <a href={BOOKING_HREF} {...BOOKING_TARGET} className={styles.bookButton}>
            Book a meeting
          </a>
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
    </header>
  );
}
