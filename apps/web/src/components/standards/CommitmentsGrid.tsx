import { COMMITMENTS, ENFORCEMENT_STRIP } from "@/lib/standardsContent";
import SectionIcon from "@/components/SectionIcon";
import styles from "./CommitmentsGrid.module.css";

// Six-commitment card grid (americanpeptides' "The Standard in
// Research-Grade Peptides", 9/2 reference), on /about since the 9/4
// Core-reference redesign took it off the homepage. Every stat line is
// true by construction or David-confirmed; the strip below cites our own
// system enforcement where the reference cites third-party badges we
// don't have. Data + rationale: lib/standardsContent.
export default function CommitmentsGrid() {
  return (
    <div>
      <div className={styles.grid}>
        {COMMITMENTS.map((commitment) => (
          <article key={commitment.number} className={styles.card}>
            <div className={styles.cardTop}>
              <span className={styles.icon}>
                <SectionIcon name={commitment.icon} />
              </span>
              <span className={styles.number}>{commitment.number}</span>
            </div>
            <h3 className={styles.title}>{commitment.title}</h3>
            <p className={styles.body}>{commitment.body}</p>
            <div className={styles.statBlock}>
              <span className={styles.stat}>{commitment.stat}</span>
              <span className={styles.statLabel}>{commitment.statLabel}</span>
            </div>
          </article>
        ))}
      </div>

      <div className={styles.strip}>
        <span className={styles.stripLabel}>Enforced in code</span>
        <div className={styles.stripItems}>
          {ENFORCEMENT_STRIP.map((item) => (
            <div key={item.value} className={styles.stripItem}>
              <span className={styles.stripValue}>{item.value}</span>
              <span className={styles.stripCaption}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
