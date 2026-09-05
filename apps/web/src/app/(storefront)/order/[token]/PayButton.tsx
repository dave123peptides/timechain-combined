"use client";

import { useState } from "react";
import { retryPayment } from "@/lib/api";
import styles from "./page.module.css";

// Pay button for a PAYMENT_PENDING crypto order. If a live checkout_url
// is already in hand (checkout just happened), it's a plain link; the
// fetch path mints a fresh Speed session server-side first.
export default function PayButton({ token, checkoutUrl }: { token: string; checkoutUrl?: string }) {
  const [url, setUrl] = useState(checkoutUrl);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (url) {
    return (
      <a href={url} className={`button ${styles.payNow}`}>
        Pay with Bitcoin &rarr;
      </a>
    );
  }

  return (
    <>
      <button
        type="button"
        className={`button ${styles.payNow}`}
        disabled={busy}
        onClick={async () => {
          setError(null);
          setBusy(true);
          try {
            const order = await retryPayment(token);
            const fresh = order.payment?.details?.checkout_url;
            if (fresh) {
              setUrl(fresh);
            } else {
              setError("Payment session could not be created — please try again in a moment.");
            }
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Creating payment session…" : "Pay with Bitcoin →"}
      </button>
      {error && (
        <p className={styles.paymentError} role="alert">
          {error}
        </p>
      )}
    </>
  );
}
