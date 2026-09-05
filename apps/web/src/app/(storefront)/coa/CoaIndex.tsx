"use client";

import { useId, useState } from "react";
import CoaGrid from "@/components/coa/CoaGrid";
import type { CoaCardGroup } from "@/lib/coa";
import styles from "./page.module.css";

// Search-as-you-type over the certificate cards. Purely a filter on the
// server-rendered list — matches product name, strength, lot and
// verification code, so a customer can paste the code off a vial's
// certificate and land on it.
export default function CoaIndex({ groups }: { groups: CoaCardGroup[] }) {
  const inputId = useId();
  const [term, setTerm] = useState("");
  const query = term.trim().toLowerCase();

  const shown = query
    ? groups.filter((group) =>
        [group.title, group.subtitle ?? "", ...group.coas.flatMap((coa) => [coa.lot, coa.verify_code])].some((value) =>
          value.toLowerCase().includes(query)
        )
      )
    : groups;

  return (
    <section className={styles.index}>
      <div className={styles.searchRow}>
        <label htmlFor={inputId} className={styles.searchLabel}>
          Find a certificate
        </label>
        <input
          id={inputId}
          type="search"
          className={styles.search}
          placeholder="Product, strength, lot or verification code"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          autoComplete="off"
        />
        <span className={styles.searchCount} aria-live="polite">
          {shown.length === groups.length
            ? `${groups.length} entries`
            : `${shown.length} of ${groups.length} entries`}
        </span>
      </div>

      {groups.length === 0 ? (
        <p className={styles.empty}>No certificates are published yet — every product is available on request.</p>
      ) : shown.length === 0 ? (
        <p className={styles.empty}>
          Nothing matches “{term.trim()}”. Try the product name, or the lot number printed on the vial.
        </p>
      ) : (
        <CoaGrid groups={shown} />
      )}
    </section>
  );
}
