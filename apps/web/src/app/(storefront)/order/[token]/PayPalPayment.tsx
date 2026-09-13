"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, capturePayPal, formatMoney, retryPayment } from "@/lib/api";
import SectionIcon from "@/components/SectionIcon";
import styles from "./page.module.css";

// The PayPal step on the order page (David, 9/13). PayPal's approval
// page can't be shown inline, so Continue to PayPal opens it in this tab
// and PayPal sends the customer back here with ?token=<PayPal order id>
// (and PayerID) appended. On that return the payment is captured through
// our API and the page re-renders as Order Confirmed. If the customer
// never makes it back, PayPal's webhook settles the order instead.
type Phase = "idle" | "capturing" | "redirecting";

export default function PayPalPayment({
  token,
  usdTotalCents,
  approveUrl,
  expiresAt,
  paypalOrderId,
  returnedOrderId,
}: {
  token: string;
  usdTotalCents: number;
  // Stored when the order was placed; null when PayPal could not be set
  // up at the time (the button then mints a fresh PayPal order).
  approveUrl: string | null;
  expiresAt: string | null;
  paypalOrderId: string | null;
  // PayPal's ?token= on the way back: the PayPal order the customer just
  // approved (or cancelled).
  returnedOrderId: string | null;
}) {
  const router = useRouter();
  const returning = returnedOrderId !== null && (paypalOrderId === null || returnedOrderId === paypalOrderId);
  const [phase, setPhase] = useState<Phase>(returning ? "capturing" : "idle");
  const [message, setMessage] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const captureStarted = useRef(false);

  // Only the browser has a clock to compare against; deciding this
  // during render would make the server and client disagree.
  useEffect(() => {
    if (!expiresAt) return;
    const deadline = Date.parse(expiresAt);
    if (!Number.isNaN(deadline)) setExpired(deadline <= Date.now());
  }, [expiresAt]);

  useEffect(() => {
    if (!returning || captureStarted.current) return;
    captureStarted.current = true;
    let cancelled = false;
    capturePayPal(token)
      .then(() => {
        if (cancelled) return;
        // Drop PayPal's query string so a reload doesn't capture again,
        // then re-render: PAID shows Order Confirmed, a capture PayPal is
        // still completing shows the note in the card.
        router.replace(`/order/${token}`);
        router.refresh();
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setPhase("idle");
        if (err instanceof ApiError && err.status === 409) {
          setMessage("Your PayPal payment was not completed. Continue to PayPal to approve it.");
        } else {
          setMessage(err instanceof Error ? err.message : "We could not confirm your PayPal payment.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [returning, token, router]);

  const continueToPayPal = async () => {
    setMessage(null);
    setPhase("redirecting");
    if (approveUrl && !expired) {
      window.location.assign(approveUrl);
      return;
    }
    // No link, or the PayPal order is past its three hours: mint a new
    // one server-side and go straight to it.
    try {
      const order = await retryPayment(token);
      const url = order.payment?.details?.approve_url;
      if (typeof url === "string" && url) {
        window.location.assign(url);
        return;
      }
      setPhase("idle");
      setMessage("PayPal could not be set up right now. Please try again in a moment, or email us with your order number.");
    } catch (err) {
      setPhase("idle");
      setMessage((err as Error).message);
    }
  };

  if (phase === "capturing") {
    return <p className={styles.cardText}>Confirming your PayPal payment. This takes a few seconds.</p>;
  }

  return (
    <div className={styles.paypal}>
      <p className={styles.cardText}>
        Approve {formatMoney(usdTotalCents)} USD on PayPal and you are sent straight back here. Your order confirms on
        its own.
      </p>
      <button
        type="button"
        className={`button buttonPill buttonAccent ${styles.paypalButton}`}
        disabled={phase === "redirecting"}
        onClick={continueToPayPal}
      >
        {phase === "redirecting" ? "Taking you to PayPal…" : "Continue to PayPal"} <SectionIcon name="external" size={16} />
      </button>
      {message && (
        <p className={styles.paymentError} role="alert">
          {message}
        </p>
      )}
    </div>
  );
}
