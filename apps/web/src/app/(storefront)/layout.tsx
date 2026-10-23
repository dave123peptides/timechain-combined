import CartDrawer from "@/components/cart/CartDrawer";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import { ORDERING_ENABLED } from "@/lib/site";

// Category navigation lives in the catalog grid itself (CategoryPills,
// lib/categories.ts), beneath the Pens | Vials toggle, and is shown for
// both lines (David, 2026-10-22; the vial site had kept categories
// internal, see the TODO(attorney-review) in lib/categories.ts).
// Product.category (the internal taxonomy) still never renders.
//
// The cart drawer exists only with ordering on (lib/site.ts): in inquiry
// mode there is no cart to open.

export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* First tabbable element on every page: lets keyboard and screen
          reader users jump past the sticky header and search combobox.
          Visually hidden until focused, see .skipLink in globals.css. */}
      <a href="#content" className="skipLink">
        Skip to content
      </a>
      <Header />
      <div id="content">{children}</div>
      <Footer />
      {/* A sibling of Header on purpose, see globals.css's stacking note. */}
      {ORDERING_ENABLED && <CartDrawer />}
    </>
  );
}
