"use client";

import { useState } from "react";
import type { ProductFaqEntry } from "@/lib/api";
import styles from "./Faq.module.css";

// One accordion implementation, shared by the PDP (ProductFaq), the
// homepage and /faq — the markup and the open/closed behaviour used to
// live only inside the product page's sections.module.css.
export default function Faq({
  entries,
  defaultOpenIndex = 0,
}: {
  entries: ProductFaqEntry[];
  defaultOpenIndex?: number | null;
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(defaultOpenIndex);

  if (entries.length === 0) return null;

  return (
    <div className={styles.list}>
      {entries.map((entry, index) => {
        const isOpen = openIndex === index;
        return (
          <div key={entry.q} className={styles.item}>
            <button
              type="button"
              className={styles.question}
              onClick={() => setOpenIndex(isOpen ? null : index)}
              aria-expanded={isOpen}
            >
              <span>{entry.q}</span>
              <span className={styles.mark} aria-hidden="true">
                {isOpen ? "−" : "+"}
              </span>
            </button>
            {isOpen && <p className={styles.answer}>{entry.a}</p>}
          </div>
        );
      })}
    </div>
  );
}
