"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { retryPayment } from "@/lib/api";
import styles from "./page.module.css";

// "Start a new payment" for a PAYMENT_PENDING Bitcoin order whose charge
// expired (or was never created). Mints a fresh OpenNode charge
// server-side, then re-renders the page so the new QR shows in place.
export default function PayButton({ token, label = "Start a new Bitcoin payment" }: { token: string; label?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
            await retryPayment(token);
            router.refresh();
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Setting up your payment…" : label}
      </button>
      {error && (
        <p className={styles.paymentError} role="alert">
          {error}
        </p>
      )}
    </>
  );
}
