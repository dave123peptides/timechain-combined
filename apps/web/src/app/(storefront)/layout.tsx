import CartDrawer from "@/components/cart/CartDrawer";
import Footer from "@/components/Footer";
import Header from "@/components/Header";

// No category navigation anywhere: benefit-named categories are
// implied-intended-use claims incompatible with RUO positioning, so
// Product.category is internal-only and never renders to customers.
// /shop is one flat alphabetical catalog (BioLongevity pattern).

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
