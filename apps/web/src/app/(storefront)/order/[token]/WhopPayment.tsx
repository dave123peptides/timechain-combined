import { formatMoney } from "@/lib/api";
import { SUPPORT_EMAIL, WHOP } from "@/lib/paymentMethods";
import PayButton from "./PayButton";
import styles from "./page.module.css";

// The card / Apple Pay step on the order page (David, 9/14): a Pay Now
// link to the Whop-hosted checkout the API created for this order
// (payment_details.checkout_url). Whop sends the customer back here
// afterwards (redirect_url) and its payment.succeeded webhook confirms
// the order; AutoRefresh in the parent card re-renders the page until
// then. A server component on purpose: the link needs no JavaScript,
// and the only interactive piece is the Try again fallback (PayButton).
export default function WhopPayment({
  token,
  checkoutUrl,
  paymentStatus,
  totalCents,
}: {
  token: string;
  checkoutUrl: string | null;
  paymentStatus: string;
  totalCents: number;
}) {
  if (paymentStatus === "processing") {
    return <p className={styles.cardText}>Payment received and being confirmed. This page updates on its own.</p>;
  }
  if (paymentStatus === "underpaid") {
    return (
      <p className={styles.cardText}>
        We received a payment that does not match this order&apos;s total. Email {SUPPORT_EMAIL} with your order
        number and we will sort it out.
      </p>
    );
  }
  if (checkoutUrl) {
    return (
      <>
        <p className={styles.cardText}>
          Click Pay Now to pay {formatMoney(totalCents)} by credit card, debit card, or Apple Pay. The payment page is
          run by {WHOP.processor} and the charge appears as &ldquo;{WHOP.merchantName}&rdquo;. You will be brought back
          here afterwards, and your order confirms automatically.
        </p>
        <a href={checkoutUrl} className={`button buttonPill buttonAccent ${styles.payNow}`}>
          Pay Now
        </a>
        <p className={styles.payHint}>Already paid? This page updates on its own within a few seconds.</p>
      </>
    );
  }
  return (
    <>
      <p className={styles.cardText}>
        {paymentStatus === "failed"
          ? "That payment did not go through. Try again below, or email us with your order number."
          : "Your card payment could not be set up. Try again below, or email us with your order number."}
      </p>
      <PayButton token={token} label="Try again" />
    </>
  );
}
