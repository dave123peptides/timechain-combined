import CartDrawer from "@/components/cart/CartDrawer";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import { ORDERING_ENABLED } from "@/lib/site";

// The cart drawer exists only with ordering on (lib/site.ts); the site's
// one action is the Book a meeting link in the header.
export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <a href="#content" className="skipLink">
        Skip to content
      </a>
      <Header />
      <div id="content">{children}</div>
      <Footer />
      {ORDERING_ENABLED && <CartDrawer />}
    </>
  );
}
