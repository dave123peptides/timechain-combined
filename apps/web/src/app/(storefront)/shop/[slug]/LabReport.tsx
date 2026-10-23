import type { ProductCoa } from "@/lib/api";
import CoaGrid from "@/components/coa/CoaGrid";
import { coaCardGroupsForProduct, distinctLabs, formatCoaDate, latestCoa } from "@/lib/coa";
import styles from "./sections.module.css";

const SUPPORT_EMAIL = "support@timechainpeptides.com";

// The Lab reports tab: one card per strength, latest certificate in
// front, every earlier one behind it in the viewer. Copy states what the
// documents ARE (issued by the lab to our supplier, per lot) and never
// what they say — the certificate carries its own figures, in context.
// Products holding none get the same honest "on request" state the site
// showed for every product before the certificates arrived.
//
// TODO(attorney-review): the four GLP-class code-name products
// (lib/compliance.ts) render this tab like any other. Nothing TimeChain
// writes — card, viewer, URL, filename — names a drug; the lab's own
// certificate, however, prints the compound's declared identity inside
// the PDF. Janesa to confirm that publishing the lab's document, as
// issued, is consistent with the no-drug-names rule before public
// launch. If not, set is_published=false on those rows (product_coas)
// — nothing else changes.
export default function LabReport({
  productName,
  productSlug,
  coas,
}: {
  productName: string;
  productSlug: string;
  coas: ProductCoa[];
}) {
  if (coas.length === 0) {
    return (
      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <span className="eyebrow">Lab Reports</span>
          <h2>Certificates of Analysis</h2>
        </div>
        <div className={styles.coaNote}>
          <span>
            No third-party certificate is published for {productName} yet. A Certificate of Analysis for a
            given batch is available on request —{" "}
            <a href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`COA request: ${productName}`)}`}>
              email {SUPPORT_EMAIL}
            </a>{" "}
            with the product and lot number.
          </span>
        </div>
      </section>
    );
  }

  const groups = coaCardGroupsForProduct(productSlug, coas);
  const labs = distinctLabs(coas);
  const latest = latestCoa(coas) ?? coas[0];

  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <span className="eyebrow">Lab Reports</span>
        <h2>Certificates of Analysis</h2>
        <p className={styles.sectionLede}>
          {coas.length} third-party {coas.length === 1 ? "certificate" : "certificates"} from {labs.join(" and ")}{" "}
          for {productName}, grouped by strength with the most recent lot in front. Each one opens the
          laboratory&apos;s own copy in a new tab and carries a verification code you can check with the lab
          directly. Most recent certificate: {formatCoaDate(latest.issued_on)}.
        </p>
      </div>
      <CoaGrid groups={groups} />
      <p className={styles.sectionNote}>
        Certificates are issued by the laboratory to our supplier for each lot it tests. If the lot printed on
        your pen or vial isn&apos;t listed here, email{" "}
        <a href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`COA request: ${productName}`)}`}>
          {SUPPORT_EMAIL}
        </a>{" "}
        with the lot number and we&apos;ll send its certificate.
      </p>
    </section>
  );
}
