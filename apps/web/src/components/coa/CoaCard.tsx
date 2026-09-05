import Link from "next/link";
import type { CoaCardGroup } from "@/lib/coa";
import { distinctLabs, formatCoaDate } from "@/lib/coa";
import styles from "./coa.module.css";

function DocumentIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  );
}

const NEW_TAB = { target: "_blank", rel: "noopener noreferrer" } as const;

// One card per strength: the latest certificate in front, every earlier
// lot listed beneath it. Every link opens the laboratory's own PDF in a
// new tab — nothing on this site re-renders or summarises a certificate.
// Every figure here is a fact about the documents (date, count, lab) and
// never a result pulled out of one.
export default function CoaCard({ group }: { group: CoaCardGroup }) {
  const [latest, ...earlier] = group.coas;
  if (!latest) return null;
  const labs = distinctLabs(group.coas);

  return (
    <article className={styles.card}>
      <span className={styles.cardIcon}>
        <DocumentIcon />
      </span>
      <h3 className={styles.cardTitle}>
        {group.productSlug ? <Link href={`/shop/${group.productSlug}`}>{group.title}</Link> : group.title}
      </h3>
      {group.subtitle && <span className={styles.cardSubtitle}>{group.subtitle}</span>}
      <span className={styles.cardDate}>Certified {formatCoaDate(latest.issued_on)}</span>
      <span className={styles.cardMeta}>
        {labs.join(" · ")} · {group.coas.length} {group.coas.length === 1 ? "report" : "reports"}
      </span>

      <a className={`button buttonPill buttonAccentOutline ${styles.cardButton}`} href={latest.pdf_url} {...NEW_TAB}>
        View certificate
      </a>
      <span className={styles.cardLot}>
        Lot {latest.lot} · {latest.verify_code}
      </span>
      {latest.tests.length > 0 && <span className={styles.cardTests}>{latest.tests.join(" · ")}</span>}
      {latest.verify_url && (
        <a className={styles.cardVerify} href={latest.verify_url} {...NEW_TAB}>
          Verify with {latest.lab}
        </a>
      )}

      {earlier.length > 0 && (
        <details className={styles.earlier}>
          <summary className={styles.earlierSummary}>
            {earlier.length} earlier {earlier.length === 1 ? "lot" : "lots"}
          </summary>
          <ul className={styles.earlierList}>
            {earlier.map((coa) => (
              <li key={coa.verify_code}>
                <a href={coa.pdf_url} {...NEW_TAB}>
                  {formatCoaDate(coa.issued_on)} · Lot {coa.lot} · {coa.verify_code}
                </a>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
