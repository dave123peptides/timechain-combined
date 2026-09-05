"use client";

import { useState } from "react";
import SectionIcon from "@/components/SectionIcon";
import styles from "./page.module.css";

// One labelled value with a Copy button (the Instant Peptides
// confirmation pattern): the customer copies the order number, amount
// and recipient straight into their payment app.
export default function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked (insecure context / permissions): the value is
      // still on screen to select by hand.
    }
  };

  return (
    <div className={styles.copyRow}>
      <div className={styles.copyText}>
        <span className={styles.copyLabel}>{label}</span>
        <span className={styles.copyValue}>{value}</span>
      </div>
      <button type="button" className={styles.copyButton} onClick={copy} aria-label={`Copy ${label}`}>
        <SectionIcon name={copied ? "check" : "copy"} size={15} />
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
