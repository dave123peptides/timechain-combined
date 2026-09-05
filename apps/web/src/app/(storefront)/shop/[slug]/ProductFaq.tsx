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
    a: "As a pre-filled 3 mL auto-injector pen. It is ready to use in a research setting — no reconstitution or diluent is involved.",
  },
  {
    q: "How should it be stored?",
    a: "Store as directed on the pen label, away from heat and light. Standard laboratory practice is refrigeration and use within the window stated on the label.",
  },
  {
    q: "Can I order multiple compounds together?",
    a: "Yes — each product ships independently, and your cart can include any combination of items from the catalog. Quantity discounts apply per SKU (see the pricing table above).",
  },
];

// Which of these renders is decided per product by whether it actually
// holds certificates — the answer must never outrun the documents.
const COA_FAQ_HELD: ProductFaqEntry = {
  q: "Is there a Certificate of Analysis for this product?",
  a: "Yes. Third-party certificates for this compound are in the Lab reports tab on this page — one per strength and lot, each opening the laboratory's own copy with a verification code you can check with the lab. If the lot printed on your pen isn't listed, email support@timechainpeptides.com with the lot number.",
};

const COA_FAQ_ON_REQUEST: ProductFaqEntry = {
  q: "Is there a Certificate of Analysis for this product?",
  a: "Not published for this compound yet. A certificate for a given batch is available on request — email support@timechainpeptides.com and reference the product and lot number. We publish certificates as we hold them.",
};

export default function ProductFaq({ faq, hasCoas }: { faq: ProductFaqEntry[]; hasCoas: boolean }) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <span className="eyebrow">Questions</span>
        <h2>Frequently Asked Questions</h2>
      </div>
      <Faq entries={[...faq, hasCoas ? COA_FAQ_HELD : COA_FAQ_ON_REQUEST, ...SHARED_FAQ]} />
    </section>
  );
}
