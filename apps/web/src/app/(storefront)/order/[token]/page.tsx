import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, formatMoney, getOrder, isUnreachable } from "@/lib/api";
import { isLivePaymentMethod, paymentOption } from "@/lib/paymentMethods";
import SectionIcon from "@/components/SectionIcon";
import PayButton from "./PayButton";
import PaymentInstructions from "./PaymentInstructions";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

const STATUS_COPY: Record<string, { tone: "pending" | "paid" | "failed"; heading: string; sub: string }> = {
  PAYMENT_PENDING: {
    tone: "pending",
    heading: "Order Placed",
    sub: "Thank you for your order. One more step: send the payment below.",
  },
  PAID: {
    tone: "paid",
    heading: "Order Confirmed",
    sub: "Payment received and confirmed. Your order is queued for fulfillment.",
  },
  PAYMENT_FAILED: {
    tone: "failed",
    heading: "Payment Not Completed",
    sub: "Payment was not completed for this order. Contact us if you believe this is an error.",
  },
};

// The confirmation / status page (Instant Peptides reference, 9/4).
// Reached right after checkout and again from the confirmation email's
// link, so it has to make sense on every visit: pending Venmo/Zelle
// orders show the transfer instructions, pending Bitcoin orders the
// hosted-checkout button, paid and failed orders their status.
export default async function OrderStatusPage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>;
  searchParams: Promise<{ pay?: string }>;
}) {
  const { token } = await params;
  const { pay } = await searchParams;
  // Only absolute-https URLs may be used as the Pay link; anything else
  // is dropped.
  const payParam = pay && /^https:\/\//.test(pay) ? pay : undefined;

  let order;
  try {
    order = await getOrder(token);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    // API down / unreachable: show the standard 404, not a crash page.
    if (isUnreachable(err)) {
      notFound();
    }
    throw err;
  }

  const address = order.shipping_address;
  const status = STATUS_COPY[order.status];
  const tone = status?.tone ?? "pending";
  const method = order.payment_method;
  const pending = order.status === "PAYMENT_PENDING";
  // Checkout-create responses carry a Speed checkout_url only while the
  // session is live; order-status fetches never do.
  const payUrl = payParam ?? order.payment?.details?.checkout_url;

  return (
    <main className="container">
      <div className={styles.wrap}>
        <header className={styles.head}>
          <span className={`${styles.mark} ${styles[`mark_${tone}`]}`}>
            <SectionIcon name={tone === "failed" ? "warning" : "check"} size={30} />
          </span>
          <h1 className={styles.heading}>{status?.heading ?? "Order Status"}</h1>
          <p className={styles.sub}>{status?.sub ?? "Payment status will update here once available."}</p>
          <div className={styles.orderLine}>
            <span className={styles.orderLabel}>Order number</span>
            <span className={styles.orderNumber}>{order.public_order_number}</span>
            {method && <span className={styles.method}>{paymentOption(method)?.label ?? method}</span>}
          </div>
        </header>

        {pending && isLivePaymentMethod(method) && <PaymentInstructions order={order} method={method} />}

        {pending && method === "crypto" && (
          <section className={styles.card}>
            <div className={styles.cardHeading}>Payment</div>
            <p className={styles.cardText}>
              Your order is reserved but not paid yet. Complete the Bitcoin payment (Lightning or on-chain) to confirm
              it — the status here updates automatically once payment is received.
            </p>
            <PayButton token={token} checkoutUrl={payUrl} />
          </section>
        )}

        <section className={styles.card}>
          <div className={styles.cardHeading}>Items</div>
          {order.items.map((item, i) => (
            <div key={i} className={styles.item}>
              <span>
                {item.name} × {item.quantity}
              </span>
              <span>{formatMoney(item.total_price_cents)}</span>
            </div>
          ))}
          <div className={styles.totalRow}>
            <span>Subtotal</span>
            <span>{formatMoney(order.subtotal_cents)}</span>
          </div>
          <div className={styles.totalRow}>
            <span>Shipping</span>
            <span>{formatMoney(order.shipping_cents)}</span>
          </div>
          <div className={`${styles.totalRow} ${styles.grand}`}>
            <span>Total</span>
            <span>{formatMoney(order.total_cents)}</span>
          </div>
        </section>

        {address && (
          <section className={styles.card}>
            <div className={styles.cardHeading}>Shipping to</div>
            <p className={styles.address}>
              {order.customer_name && (
                <>
                  <strong>{order.customer_name}</strong>
                  <br />
                </>
              )}
              {address.line1}
              <br />
              {address.line2 && (
                <>
                  {address.line2}
                  <br />
                </>
              )}
              {address.city}, {address.region} {address.postal_code}
              <br />
              {address.country}
              {order.customer_phone && (
                <>
                  <br />
                  {order.customer_phone}
                </>
              )}
            </p>
          </section>
        )}

        <div className={styles.actions}>
          <Link href="/shop" className={`button buttonPill buttonPrimary ${styles.continue}`}>
            Continue Shopping
          </Link>
          <p className={styles.keep}>Keep this page&apos;s link — it&apos;s how you check on this order.</p>
        </div>
      </div>
    </main>
  );
}
