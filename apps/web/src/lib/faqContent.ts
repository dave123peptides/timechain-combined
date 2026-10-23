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
//  - Shipping times, carrier, cutoffs, processing or reply times.
//  - Returns policy. Not decided.
//  - Any purity percentage or third-party test result. None exist yet.
//  - Prices and volume tiers. Hidden until the wholesale sheet exists
//    (David, 2026-10-22); pricing is given on the call.
export const SITE_FAQ: ProductFaqEntry[] = [
  {
    q: "Who do you supply?",
    a: "Research organizations and medical practices ordering in quantity. Everything in this catalog is supplied strictly for laboratory and research use: these are not drugs, dietary supplements, cosmetics, or food; they are not intended for human or veterinary use; and they are not intended to diagnose, treat, cure, or prevent any disease.",
  },
  {
    q: "How do I order?",
    a: "Book a meeting. On the call we go through the catalog for your practice, confirm formats, strengths and quantities, and arrange the order directly with you. No payment is taken on this site.",
  },
  {
    q: "Why are there no prices on the site?",
    a: "Pricing depends on format, strength and quantity, and is given on the call for exactly what you need.",
  },
  {
    q: "What formats do the products come in?",
    a: "Two. Pens are pre-filled 3 mL auto-injector pens, ready to use in a research setting with no reconstitution. Vials hold lyophilized (freeze-dried) powder and are reconstituted with an appropriate diluent before use. Many compounds are offered in both formats on one product page. Those two formats are enforced in our systems, not just stated as policy.",
  },
  {
    q: "Where are your products compounded and tested?",
    a: "Raw peptide material originates overseas, as it does for effectively every supplier in this market. What differs is the rest of the chain: our products are compounded, tested, and verified in the United States rather than only being imported and resold.",
  },
  {
    q: "Do you provide a Certificate of Analysis?",
    a: "Yes. Third-party certificates are published on each product page under Lab reports, and collected on the Certificates of Analysis page, one per strength and lot, each opening the laboratory's own copy with a verification code you can check with the lab. We link to the certificate rather than quoting a purity figure from it. For a lot that isn't listed yet, ask on the call or email support@timechainpeptides.com with the product and lot number.",
  },
  {
    q: "How should the products be stored?",
    a: "Store as directed on the label, away from heat and light. Standard laboratory practice is refrigeration and use within the window stated on the label.",
  },
  {
    q: "What happens on the call?",
    a: "We go through the catalog with you: which compounds, formats and strengths fit your practice, the quantities you need, the documentation your compliance needs, and pricing. Then the order is arranged directly.",
  },
];
