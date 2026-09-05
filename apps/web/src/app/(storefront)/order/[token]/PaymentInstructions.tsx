import type { Order } from "@/lib/api";
import { formatMoney } from "@/lib/api";
import { BUSINESS_NAME, SUPPORT_EMAIL, VENMO, ZELLE, type LivePaymentMethod } from "@/lib/paymentMethods";
import SectionIcon from "@/components/SectionIcon";
import CopyField from "./CopyField";
import styles from "./page.module.css";

// What a Venmo or Zelle customer sees after placing the order (Instant
// Peptides reference, 9/4): the memo warning, then everything to copy
// into the payment app. Zelle lists the recipient details; Venmo gives
// the order number and a link straight to the profile. The amount is
// the order's server-computed total, formatted, never recomputed here.
export default function PaymentInstructions({ order, method }: { order: Order; method: LivePaymentMethod }) {
  const amount = formatMoney(order.total_cents);
  const memoField = method === "zelle" ? "memo" : "note";
  const app = method === "zelle" ? "Zelle" : "Venmo";

  return (
    <section className={styles.pay}>
      <div className={styles.warning} role="alert">
        <SectionIcon name="warning" size={30} />
        <p className={styles.warningTitle}>
          Do not reference peptides, product names, or any product information in the {app} {memoField}.
        </p>
        <p className={styles.warningBody}>Enter only your order number. Nothing else.</p>
      </div>

      <div className={styles.payCard}>
        <p className={styles.payLede}>
          Send <strong>{amount}</strong> via <strong>{app}</strong> using the information below.
        </p>
        <div className={styles.important}>
          <span className={styles.importantLabel}>Important</span>
          Enter ONLY “{order.public_order_number}” in the {memoField} field. Do not add anything else.
        </div>

        <CopyField label={`Order number (${memoField})`} value={order.public_order_number} />
        <CopyField label="Amount" value={amount} />
        {method === "zelle" ? (
          <>
            <CopyField label="Recipient" value={ZELLE.recipient} />
            <CopyField label="Name on the account" value={ZELLE.accountName} />
          </>
        ) : (
          <>
            <CopyField label="Venmo" value={VENMO.handle} />
            <a href={VENMO.url} className={`button buttonPill buttonAccent ${styles.payLink}`} target="_blank" rel="noopener noreferrer">
              Open our Venmo profile <SectionIcon name="external" size={16} />
            </a>
            <p className={styles.payLinkHint}>Opens venmo.com in a new tab. Send {amount} to {VENMO.handle} with “{order.public_order_number}” as the note.</p>
          </>
        )}
      </div>

      <div className={styles.payNote}>
        <p>
          Your order is reserved as pending and ships once the transfer is received and matched to your order number. If
          you sent payment and haven&apos;t received a confirmation email within a few hours, or you&apos;re unable to
          complete the payment, email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with your order number.
        </p>
        <p className={styles.payNoteSmall}>Payments are received by {BUSINESS_NAME}.</p>
      </div>
    </section>
  );
}
