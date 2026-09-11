import Link from "next/link";
import { notFound } from "next/navigation";
import QRCode from "qrcode";
import { ApiError, formatMoney, getOrder, isUnreachable, type PaymentDetails } from "@/lib/api";
import { SUPPORT_EMAIL, isHostedCheckoutMethod, isLivePaymentMethod, paymentMethodLabel } from "@/lib/paymentMethods";
import SectionIcon from "@/components/SectionIcon";
import AutoRefresh from "./AutoRefresh";
import BitcoinPayment, { type BitcoinRail } from "./BitcoinPayment";
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

// The QR codes are drawn here, on the server, so the client bundle
// carries no QR library and the page works without JavaScript.
async function qrSvg(text: string): Promise<string> {
  return QRCode.toString(text, { type: "svg", margin: 1, errorCorrectionLevel: "M" });
}

async function bitcoinRails(details: PaymentDetails): Promise<{ lightning: BitcoinRail | null; onchain: BitcoinRail | null }> {
  const invoice = details.lightning_invoice ?? null;
  const address = details.chain_address ?? null;
  const btc = details.amount_sats != null ? (details.amount_sats / 1e8).toFixed(8) : null;
  const bitcoinUri = details.bitcoin_uri ?? (address ? `bitcoin:${address}${btc ? `?amount=${btc}` : ""}` : null);
  // Upper-case BOLT11 keeps the QR in alphanumeric mode (a much smaller code).
  const lightning = invoice ? { svg: await qrSvg(invoice.toUpperCase()), uri: `lightning:${invoice}`, value: invoice } : null;
  const onchain = address && bitcoinUri ? { svg: await qrSvg(bitcoinUri), uri: bitcoinUri, value: address } : null;
  return { lightning, onchain };
}

// The confirmation / status page (Instant Peptides reference, 9/4).
// Reached right after checkout and again from the confirmation email's
// link, so it has to make sense on every visit: pending Venmo/Zelle
// orders show the transfer instructions; pending Bitcoin orders show the
// payment itself (QR, open in wallet) and refresh on their own until
// OpenNode's webhook confirms (David, 9/11: no bounce to OpenNode); paid
// and failed orders show their status.
export default async function OrderStatusPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

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
  const hosted = pending && isHostedCheckoutMethod(method);
  const paymentStatus = order.payment_status ?? "pending";
  const sub = hosted ? "Thank you for your order. One more step: pay with Bitcoin below." : status?.sub;
  const details = hosted ? order.payment_details ?? null : null;
  const rails = details ? await bitcoinRails(details) : null;
  const payable = rails !== null && (rails.lightning !== null || rails.onchain !== null);

  return (
    <main className="container">
      <div className={styles.wrap}>
        <header className={styles.head}>
          <span className={`${styles.mark} ${styles[`mark_${tone}`]}`}>
            <SectionIcon name={tone === "failed" ? "warning" : "check"} size={30} />
          </span>
          <h1 className={styles.heading}>{status?.heading ?? "Order Status"}</h1>
          <p className={styles.sub}>{sub ?? "Payment status will update here once available."}</p>
          <div className={styles.orderLine}>
            <span className={styles.orderLabel}>Order number</span>
            <span className={styles.orderNumber}>{order.public_order_number}</span>
            {method && <span className={styles.method}>{paymentMethodLabel(method) ?? method}</span>}
          </div>
        </header>

        {pending && isLivePaymentMethod(method) && <PaymentInstructions order={order} method={method} />}

        {hosted && (
          <section className={styles.card}>
            <div className={styles.cardHeading}>Pay with Bitcoin</div>
            {paymentStatus === "processing" ? (
              <p className={styles.cardText}>
                Payment detected. Waiting for the Bitcoin network to confirm it. This page updates on its own.
              </p>
            ) : paymentStatus === "underpaid" ? (
              <p className={styles.cardText}>
                We received a partial payment for this order. Email {SUPPORT_EMAIL} with your order number and we will
                sort it out.
              </p>
            ) : payable && details ? (
              <BitcoinPayment
                amountSats={details.amount_sats ?? null}
                usdTotalCents={order.total_cents}
                lightning={rails.lightning}
                onchain={rails.onchain}
                expiresAt={details.expires_at ?? null}
                hostedUrl={details.checkout_url ?? null}
              />
            ) : (
              <>
                <p className={styles.cardText}>
                  {paymentStatus === "expired"
                    ? "This payment request expired. Start a new one below; your order is still reserved."
                    : "Your Bitcoin payment could not be set up. Try again below, or email us with your order number."}
                </p>
                <PayButton token={token} />
              </>
            )}
            <AutoRefresh />
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
          {order.discount_cents > 0 && (
            <div className={styles.totalRow}>
              <span>Discount{order.discount_code ? ` (${order.discount_code})` : ""}</span>
              <span>&minus;{formatMoney(order.discount_cents)}</span>
            </div>
          )}
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
