import Link from "next/link";
import PageBanner from "@/components/PageBanner";
import CommitmentsGrid from "@/components/standards/CommitmentsGrid";
import ProofSection from "@/components/standards/ProofSection";
import VerificationPipeline from "@/components/standards/VerificationPipeline";
import styles from "./page.module.css";

export const metadata = { title: "About & Quality | TimeChain" };

// Real claims only. Several statements previously on this page could not
// be backed and have been removed rather than softened:
//  - "Every batch we ship carries a current Certificate of Analysis" and
//    "No batch ships without paperwork" — third-party certificates now
//    exist and are published per lot (product_coas, the PDP's Lab reports
//    tab, /coa), but not for every product or every lot, so the
//    universal claim stays out. Say what is held; link to it.
//  - "verified purity" — the certificates carry purity figures, but this
//    site never quotes one outside the document (see ProofSection).
//  - "liquid multi-mL vial formats" — nothing non-lyophilized can be sold
//    here at all; ProductVariant._validate_is_sellable rejects it.
//
// Since the 9/4 Core-reference redesign this page also carries the
// standards content that used to fill the homepage (CommitmentsGrid,
// VerificationPipeline, ProofSection — all from lib/standardsContent,
// where the real-claims rule is spelled out), between the prose sections.
export default function AboutPage() {
  return (
    <main>
      <PageBanner variant="light" eyebrow="About & Quality" title="About TimeChain">
        <p className={styles.bannerLede}>
          Timechain exists to give research partners a peptide source they can defend — a documented supply chain,
          US compounding and testing, and honest answers about what we do and don&apos;t know.
        </p>
      </PageBanner>

      <div className={styles.prose}>
        <h2>Who we are</h2>
        <p>
          Timechain Peptides is the trading name of Timechain Ventures LLC, a Florida company supplying research
          peptides to laboratories and research organizations in the United States.
        </p>

        <h2>Where our material comes from</h2>
        <p>
          We&apos;ll be straightforward about this, because most of the industry isn&apos;t: raw peptide material
          originates overseas, predominantly in China. That is true of effectively every supplier in this market,
          including the ones that don&apos;t say so.
        </p>
        <p>
          What differs is what happens next. Our products are compounded in the United States, tested in the United
          States, and verified in the United States before they are listed. Many competitors compound abroad, or
          import finished material and test only on arrival. We keep that chain domestic.
        </p>

        <h2>What &ldquo;verified&rdquo; means here</h2>
        <p>
          Every product offered on this site is matched and confirmed against supplier records before it can be
          listed — and that isn&apos;t a policy statement, it&apos;s enforced in our systems. A product with no
          confirmed supplier mapping cannot be made available for sale, and if a supplier record later changes or
          disappears, the affected items are pulled from sale automatically rather than waiting on a human to notice.
        </p>
      </div>

      <section className={styles.why}>
        <div className="container">
          <div className={styles.whyHead}>
            <span className="eyebrow">Why choose TimeChain</span>
            <h2>A Standard You Can Verify</h2>
            <p className={styles.whyLede}>
              Six commitments — each one something you can check, most of them enforced by our systems rather than
              promised in copy.
            </p>
          </div>
          <CommitmentsGrid />
        </div>
      </section>

      <VerificationPipeline />

      <div className={styles.prose}>
        <h2>Certificates of Analysis</h2>
        <p>
          Third-party Certificates of Analysis are published on each product page under Lab reports, and collected
          on our <Link href="/coa">Certificates of Analysis</Link> page — one per strength and lot, issued by the
          laboratory to our supplier, each opening the lab&apos;s own copy in a new tab with a verification code you
          can check with the lab. We link to the certificate rather than quoting a purity percentage from it, which
          is why you won&apos;t find a headline number anywhere on this site. For a lot not yet listed, email{" "}
          <a href="mailto:support@timechainpeptides.com">support@timechainpeptides.com</a> and reference the product
          and lot number.
        </p>

        <h2>Our format</h2>
        <p>
          Everything here ships as a lyophilized (freeze-dried) vial. No pens, no pre-constituted formats — that
          constraint is enforced in our catalog systems, not just stated as a preference. Lyophilized material is
          more stable in transit and storage, and it leaves reconstitution under the researcher&apos;s control.
        </p>
      </div>

      <ProofSection />

      <div className={styles.prose}>
        <h2>Research use only</h2>
        <p>
          Everything we supply is for laboratory and research use. These are not drugs, dietary supplements,
          cosmetics, or food; they are not intended for human or veterinary use; and they are not intended to
          diagnose, treat, cure, or prevent any disease. See our{" "}
          <Link href="/research-use-only">Research Use Only</Link> page for the full statement.
        </p>

        <h2>Get in touch</h2>
        <p>
          Questions about a product, a document request, or a research partnership — our{" "}
          <Link href="/contact">contact page</Link> has the fastest way to reach us.
        </p>
      </div>
    </main>
  );
}
