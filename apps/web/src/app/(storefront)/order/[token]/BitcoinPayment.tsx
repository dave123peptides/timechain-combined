"use client";

import { useEffect, useState } from "react";
import { formatMoney } from "@/lib/api";
import SectionIcon from "@/components/SectionIcon";
import styles from "./page.module.css";

export type BitcoinRail = {
  // The QR as an SVG string, rendered server-side (lib "qrcode").
  svg: string;
  // What "Open in wallet" launches: lightning:<invoice> or the bitcoin: URI.
  uri: string;
  // The raw value to copy: the BOLT11 invoice or the address.
  value: string;
};

// The Bitcoin payment itself, on our page (David, 9/11): the customer
// scans or taps, never leaves the site, and the page confirms on its own
// once OpenNode's webhook lands (AutoRefresh). Lightning first — it
// confirms in seconds — with on-chain a tab away, like OpenNode's page.
export default function BitcoinPayment({
  amountSats,
  usdTotalCents,
  lightning,
  onchain,
  expiresAt,
  hostedUrl,
}: {
  amountSats: number | null;
  usdTotalCents: number;
  lightning: BitcoinRail | null;
  onchain: BitcoinRail | null;
  expiresAt: string | null;
  hostedUrl: string | null;
}) {
  const [tab, setTab] = useState<"lightning" | "onchain">(lightning ? "lightning" : "onchain");
  const [copied, setCopied] = useState(false);
  const [minutesLeft, setMinutesLeft] = useState<number | null>(null);

  // Computed on the client only (the server has no local clock to agree
  // with), refreshed every 30 s.
  useEffect(() => {
    if (!expiresAt) return;
    const deadline = Date.parse(expiresAt);
    if (Number.isNaN(deadline)) return;
    const tick = () => setMinutesLeft(Math.max(0, Math.round((deadline - Date.now()) / 60000)));
    tick();
    const timer = window.setInterval(tick, 30000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  const rail = tab === "lightning" ? lightning : onchain;
  const btc = amountSats != null ? (amountSats / 1e8).toFixed(8) : null;

  const copy = async () => {
    if (!rail) return;
    try {
      await navigator.clipboard.writeText(rail.value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked: the value is still on screen to select by hand.
    }
  };

  return (
    <div className={styles.btc}>
      {lightning && onchain && (
        <div className={styles.btcTabs} role="tablist" aria-label="Payment rail">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "lightning"}
            className={`${styles.btcTab} ${tab === "lightning" ? styles.btcTabActive : ""}`}
            onClick={() => setTab("lightning")}
          >
            Lightning
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "onchain"}
            className={`${styles.btcTab} ${tab === "onchain" ? styles.btcTabActive : ""}`}
            onClick={() => setTab("onchain")}
          >
            On-chain
          </button>
        </div>
      )}

      <div className={styles.btcAmount}>
        {btc && <span className={styles.btcAmountBtc}>{btc} BTC</span>}
        <span className={styles.btcAmountUsd}>{btc ? "≈ " : ""}{formatMoney(usdTotalCents)} USD</span>
      </div>

      {rail && (
        <>
          <div className={styles.btcQr} dangerouslySetInnerHTML={{ __html: rail.svg }} />
          <a href={rail.uri} className={`button buttonPill buttonAccent ${styles.btcOpen}`}>
            Open in wallet
          </a>
          <div className={styles.btcCopy}>
            <span className={styles.btcCopyLabel}>{tab === "lightning" ? "Lightning invoice" : "Bitcoin address"}</span>
            <code className={styles.btcCopyValue}>{rail.value}</code>
            <button type="button" className={styles.copyButton} onClick={copy} aria-label="Copy">
              <SectionIcon name="copy" size={14} /> {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </>
      )}

      <p className={styles.cardText}>
        {tab === "lightning"
          ? "Scan with any Lightning wallet, or tap Open in wallet. Your order confirms on its own within seconds of paying."
          : "Send exactly this amount to the address above. Your order confirms on its own after one network confirmation, usually within the hour."}
        {minutesLeft !== null && (
          <>
            {" "}
            {minutesLeft > 0
              ? `This payment request is good for about ${minutesLeft} more minute${minutesLeft === 1 ? "" : "s"}.`
              : "This payment request has expired. Reload the page to start a new one."}
          </>
        )}
      </p>

      {hostedUrl && (
        <p className={styles.btcFallback}>
          Having trouble? <a href={hostedUrl}>Pay on OpenNode&apos;s page instead</a>.
        </p>
      )}
    </div>
  );
}
