import Link from "next/link";
import { PURITY_GAPS } from "@/lib/standardsContent";
import styles from "./ProofSection.module.css";

// Dark education section modeled on americanpeptides' "What 99% pure
// doesn't tell you" (David's 9/2 reference). Same skeleton — dark ground,
// light two-column cards, closing display line — but the argument is
// inverted to fit TimeChain's committed position: where AP closes each
// card with "and that's why we run test X", we have no testing program to
// cite, so the section closes on the documentation-first stance the about
// page already commits to ("we don't publish numbers we can't show you").
// The card content itself is methodology education, not claims — see
// PURITY_GAPS' docstring before editing any copy here.
export default function ProofSection() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.head}>
          <span className={`eyebrow ${styles.eyebrow}`}>Beyond Purity</span>
          <h2 className={styles.title}>What a purity number doesn&apos;t tell you.</h2>
          <p className={styles.sub}>A purity test measures one thing. Here are four things it can&apos;t see.</p>
          <p className={styles.lede}>
            Every supplier in this market quotes a purity percentage. But HPLC and mass spectrometry — the tests
            behind that number — characterize the molecule, not what surrounds it. A sample can test 99% pure and
            still carry bacterial endotoxins, heavy metals, or live microbial contamination the chromatogram will
            never show. That&apos;s why you won&apos;t find a headline number anywhere on this site: we&apos;d
            rather hand you the batch paperwork than a percentage stripped of its context.
          </p>
        </div>

        <div className={styles.grid}>
          {PURITY_GAPS.map((gap) => (
            <article key={gap.number} className={styles.card}>
              <span className={styles.chip}>
                {gap.number} — {gap.tag}
              </span>
              <h3 className={styles.cardTitle}>{gap.title}</h3>
              <p className={styles.cardSub}>{gap.sub}</p>
              <div className={styles.block}>
                <span className={styles.blockLabel}>{gap.missesLabel}</span>
                <p className={styles.blockBody}>{gap.misses}</p>
              </div>
              <div className={styles.block}>
                <span className={styles.blockLabel}>{gap.mattersLabel}</span>
                <p className={styles.blockBody}>{gap.matters}</p>
              </div>
            </article>
          ))}
        </div>

        <div className={styles.closing}>
          <p className={styles.closingLine}>
            A number is a claim. <span className={styles.closingAccent}>A record is proof.</span>
          </p>
          <Link href="/coa" className={styles.closingLink}>
            See the batch certificates &rarr;
          </Link>
        </div>
      </div>
    </section>
  );
}
