"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Re-renders the (force-dynamic) order page every few seconds while a
// Bitcoin, PayPal or card payment is pending, so it flips to "Order
// Confirmed" on its own once the provider's webhook lands — Lightning
// within seconds, on-chain after one confirmation, Whop a few seconds
// after the customer is sent back. Stops after maxMs, or when the pending card
// unmounts because the order is no longer pending. Renders nothing.
export default function AutoRefresh({
  intervalMs = 8000,
  maxMs = 15 * 60 * 1000,
}: {
  intervalMs?: number;
  maxMs?: number;
}) {
  const router = useRouter();

  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => {
      if (Date.now() - started > maxMs) {
        clearInterval(timer);
        return;
      }
      router.refresh();
    }, intervalMs);
    return () => clearInterval(timer);
  }, [router, intervalMs, maxMs]);

  return null;
}
