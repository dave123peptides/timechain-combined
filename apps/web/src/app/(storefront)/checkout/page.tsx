import { redirect } from "next/navigation";
import { ORDERING_ENABLED } from "@/lib/site";
import CheckoutPage from "./CheckoutPage";

// Inquiry mode (lib/site.ts): no checkout. The API refuses checkout
// writes as well (ORDERING_ENABLED), so this redirect is the friendly
// face of that refusal, not the thing enforcing it. The three-step
// checkout (CheckoutPage, a client component) returns with ordering.
export default function Page() {
  if (!ORDERING_ENABLED) redirect("/contact");
  return <CheckoutPage />;
}
