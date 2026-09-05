import CartDrawer from "@/components/cart/CartDrawer";
import Footer from "@/components/Footer";
import Header from "@/components/Header";

// Category navigation lives in the catalog grid itself (CategoryPills,
// lib/categories.ts) — David's 2026-09-05 decision for the pens site.
// The vial site kept every category internal because benefit-named
// groups read as intended-use claims; that concern is recorded as a
// TODO(attorney-review) in lib/categories.ts. Product.category (the
// internal taxonomy) still never renders to customers.

export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* First tabbable element on every page: lets keyboard and screen
          reader users jump past the sticky header and search combobox.
          Visually hidden until focused — see .skipLink in globals.css. */}
      <a href="#content" className="skipLink">
        Skip to content
      </a>
      <Header />
      <div id="content">{children}</div>
      <Footer />
      {/* A sibling of Header on purpose — see globals.css's stacking note. */}
      <CartDrawer />
    </>
  );
}
