import { redirect } from "next/navigation";
import { ORDERING_ENABLED } from "@/lib/site";
import CartPage from "./CartPage";

// Inquiry mode (lib/site.ts): there is no cart, so /cart sends the
// visitor to the contact page instead of an empty cart. The full-page
// cart (CartPage, a client component) returns with ordering.
export default function Page() {
  if (!ORDERING_ENABLED) redirect("/contact");
  return <CartPage />;
}
