import type { ProductFaqEntry } from "@/lib/api";
import Faq from "@/components/Faq";
import styles from "./sections.module.css";

// Shown on every product page, in addition to any compound-specific
// entries from Product.content.faq — these are operational facts true
// for the whole catalog, not worth repeating in every product's content
// JSON. Keep in sync with reality (form/shipping/consent behavior), not
// with any single product.
const SHARED_FAQ: ProductFaqEntry[] = [
  {
    q: "What form does this ship in?",
    a: "In the format selected above. A pen is a pre-filled 3 mL auto-injector pen, ready to use in a research setting with no reconstitution or diluent involved. A vial holds lyophilized (freeze-dried) powder and is reconstituted with an appropriate diluent before use. Compounds offered in both formats show both.",
  },
  {
    q: "How should it be stored?",
    a: "Store as directed on the label, away from heat and light. Standard laboratory practice is refrigeration and use within the window stated on the label.",
  },
  {
    q: "How do I order it, and in what quantities?",
    a: "Book a meeting. Any quantity and any mix of compounds, formats and strengths can be arranged; on the call we confirm availability, documentation and pricing for what you need, then arrange the order directly.",
  },
];

// Rendered only for a product that actually holds certificates: the
// answer must never outrun the documents. While no COAs are loaded the
// question is left out entirely.
const COA_FAQ_HELD: ProductFaqEntry = {
  q: "Is there a Certificate of Analysis for this product?",
  a: "Yes. Third-party certificates for this compound are in the Lab reports tab on this page, one per strength and lot, each opening the laboratory's own copy with a verification code you can check with the lab. If the lot printed on your pen or vial isn't listed, email support@timechainpeptides.com with the lot number.",
};

export default function ProductFaq({ faq, hasCoas }: { faq: ProductFaqEntry[]; hasCoas: boolean }) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <span className="eyebrow">Questions</span>
        <h2>Frequently Asked Questions</h2>
      </div>
      <Faq entries={[...faq, ...(hasCoas ? [COA_FAQ_HELD] : []), ...SHARED_FAQ]} />
    </section>
  );
}
