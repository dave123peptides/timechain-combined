import CartDrawer from "@/components/cart/CartDrawer";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import RequestDrawer from "@/components/request/RequestDrawer";
import { ORDERING_ENABLED } from "@/lib/site";

// The order request drawer is the site's working surface (every Add to
// request opens it); the cart drawer exists only with ordering on
// (lib/site.ts). Both render here, as siblings of the header, because the
// sticky header forms a stacking context nothing inside it can escape.
export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <a href="#content" className="skipLink">
        Skip to content
      </a>
      <Header />
      <div id="content">{children}</div>
      <Footer />
      <RequestDrawer />
      {ORDERING_ENABLED && <CartDrawer />}
    </>
  );
}
