import Link from "next/link";
import SectionIcon from "@/components/SectionIcon";
import styles from "./QualitySection.module.css";

// Quality (Ascend's "read the certificate before you buy", BioLongevity's
// COA library): the sourcing claim David made for the FAQ, and what a
// Certificate of Analysis covers. The card lists the fields of a
// certificate, never a result: the number stays inside the document, in
// its own context (see ProofSection's note on /coa).
const COVERS = ["Identity of the compound", "Purity assay", "Lot number", "Date issued", "Issuing laboratory", "Verification code"];

export default function QualitySection() {
  return (
    <section className={styles.section}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <span className="eyebrow">Quality</span>
          <h2>
            Every batch, <em>documented.</em>
          </h2>
          <p className={styles.lede}>
            Raw peptide material originates overseas, as it does for effectively every supplier in this market. What
            differs is the rest of the chain: our products are compounded, tested and verified in the United States
            rather than only being imported and resold.
          </p>
          <p className={styles.body}>
            A Certificate of Analysis for any batch is available on request. Published certificates open the
            laboratory&apos;s own copy and carry a verification code you can check with the lab directly. We link to
            the document rather than quoting a figure from it.
          </p>
          <div className={styles.actions}>
            <Link href="/coa" className="button buttonAccentOutline">
              Certificates of Analysis
            </Link>
          </div>
        </div>

        <div className={styles.card} aria-label="What a certificate covers">
          <div className={styles.cardHead}>
            <span className={styles.cardIcon}>
              <SectionIcon name="document" size={20} />
            </span>
            <div>
              <span className={styles.cardEyebrow}>Certificate of Analysis</span>
              <span className={styles.cardTitle}>What the document covers</span>
            </div>
          </div>
          <ul className={styles.rows}>
            {COVERS.map((row) => (
              <li key={row} className={styles.row}>
                <span>{row}</span>
                <SectionIcon name="check" size={16} />
              </li>
            ))}
          </ul>
          <p className={styles.cardNote}>Results are read on the certificate itself, with the laboratory.</p>
        </div>
      </div>
    </section>
  );
}
