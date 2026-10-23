import type { ProductFaqEntry } from "@/lib/api";

// Site-wide FAQ, shared by the homepage section and /faq so the two can't
// drift. Product-specific questions live in Product.content.faq and the
// catalog-wide operational ones in ProductFaq's SHARED_FAQ.
//
// Every answer here is verifiable against this codebase or against a fact
// David has confirmed. Where neither is true, the question is omitted
// rather than answered vaguely.
//
// DELIBERATELY ABSENT, do not add without confirmed facts:
//  - Shipping times, carrier, same-day cutoff, processing time. /shipping
//    is on hold and the cutoff is unconfirmed; a guessed answer here is a
//    published shipping claim by another name.
//  - Returns policy. Not decided.
//  - Free shipping. No threshold exists.
//  - Any purity percentage or third-party test result. None exist yet.
//  - Payment methods and volume discounts. This site takes no payments
//    (David, 2026-10-22); pricing is discussed when you contact us.
export const SITE_FAQ: ProductFaqEntry[] = [
  {
    q: "What does “Research Use Only” mean?",
    a: "Everything in this catalog is supplied strictly for laboratory and research use. These are not drugs, dietary supplements, cosmetics, or food; they are not intended for human or veterinary use; and they are not intended to diagnose, treat, cure, or prevent any disease. Every order is arranged on that understanding.",
  },
  {
    q: "What formats do the products come in?",
    a: "Two. Pens are pre-filled 3 mL auto-injector pens, ready to use in a research setting with no reconstitution. Vials hold lyophilized (freeze-dried) powder and are reconstituted with an appropriate diluent before use. Many compounds are offered in both formats on one product page; the Pens and Vials toggle above the catalog shows one line at a time. Those two formats are enforced in our systems, not just stated as policy: nothing else can be listed here.",
  },
  {
    q: "How do I order?",
    a: "This site does not take payments. Browse the catalog, then book a meeting from the Contact page or email support@timechainpeptides.com. We go over the compounds, formats, quantities and documentation you need and arrange the order directly with you.",
  },
  {
    q: "How should the products be stored?",
    a: "Store as directed on the label, away from heat and light. Standard laboratory practice is refrigeration and use within the window stated on the label.",
  },
  {
    q: "Do you provide a Certificate of Analysis?",
    a: "Yes. Third-party certificates are published on each product page under Lab reports, and collected on the Certificates of Analysis page, one per strength and lot, each opening the laboratory's own copy with a verification code you can check with the lab. We link to the certificate rather than quoting a purity figure from it. For a lot that isn't listed yet, email support@timechainpeptides.com with the product and lot number.",
  },
  {
    q: "Where are your products compounded and tested?",
    a: "Raw peptide material originates overseas, as it does for effectively every supplier in this market. What differs is the rest of the chain: our products are compounded, tested, and verified in the United States rather than only being imported and resold.",
  },
];
