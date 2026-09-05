import { PIPELINE_STEPS } from "@/lib/standardsContent";
import SectionIcon from "@/components/SectionIcon";
import styles from "./VerificationPipeline.module.css";

// Dark "the standard" wall (americanpeptides' "Every batch survives 18
// days of scrutiny", 9/2 reference). Their wall describes a seven-layer
// third-party testing program; no such program exists here to describe,
// so this renders the thing TimeChain actually has — the listing gate,
// which is real and mostly machine-enforced (see PIPELINE_STEPS). The
// highlighted card carries the one number we can stand behind absolutely:
// zero ways to list an unverified product.
export default function VerificationPipeline() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.head}>
          <div>
            <span className={styles.chip}>The Listing Standard</span>
            <h2 className={styles.title}>
              Every product clears <span className={styles.accent}>the same gate</span> before it&apos;s ever
              offered for sale.
            </h2>
          </div>
          <p className={styles.headBody}>
            Most storefronts list whatever the supplier sends. Ours can&apos;t: listing is gated in software —
            supplier match, domestic handling, format checks — and if the record behind a product changes, it
            comes off sale automatically.
          </p>
        </div>

        <div className={styles.grid}>
          {PIPELINE_STEPS.map((step) => (
            <article key={step.number} className={step.highlight ? styles.cardHighlight : styles.card}>
              <span className={styles.number}>{step.number}</span>
              <span className={styles.icon}>
                <SectionIcon name={step.icon} size={18} />
              </span>
              {step.highlight ? (
                <div className={styles.highlightStat}>
                  {/* The stat row replaces the title visually; the h3 stays
                      for a consistent heading outline. */}
                  <h3 className="sr-only">{step.title}</h3>
                  <span className={styles.stat}>{step.highlight.stat}</span>
                  <span className={styles.statLabel}>{step.highlight.statLabel}</span>
                </div>
              ) : (
                <h3 className={styles.cardTitle}>{step.title}</h3>
              )}
              <p className={styles.cardBody}>{step.body}</p>
            </article>
          ))}
        </div>

        <p className={styles.footnote}>Gated by our catalog systems — every product, no exceptions.</p>
      </div>
    </section>
  );
}
