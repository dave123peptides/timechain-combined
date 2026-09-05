import type { ProductFaqEntry } from "@/lib/api";

// Site-wide FAQ, shared by the homepage section and /faq so the two can't
// drift. Product-specific questions live in Product.content.faq and the
// catalog-wide operational ones in ProductFaq's SHARED_FAQ.
//
// Every answer here is verifiable against this codebase or against a fact
// David has confirmed. Where neither is true, the question is omitted
// rather than answered vaguely.
//
// DELIBERATELY ABSENT — do not add without confirmed facts:
//  - Shipping times, carrier, same-day cutoff, processing time. /shipping
//    is on hold and the cutoff is unconfirmed; a guessed answer here is a
//    published shipping claim by another name.
//  - Returns policy. Not decided.
//  - Free shipping. No threshold exists.
//  - Any purity percentage or third-party test result. None exist yet.
export const SITE_FAQ: ProductFaqEntry[] = [
  {
    q: "What does “Research Use Only” mean?",
    a: "Everything in this catalog is supplied strictly for laboratory and research use. These are not drugs, dietary supplements, cosmetics, or food; they are not intended for human or veterinary use; and they are not intended to diagnose, treat, cure, or prevent any disease. Purchasing requires acknowledging this at checkout.",
  },
  {
    q: "What form do the products ship in?",
    a: "Every product on this site ships as a pre-filled 3 mL auto-injector pen. That is enforced in our systems, not just stated as policy — any other format cannot be listed for sale here at all. Pens are ready to use in a research setting; no reconstitution or diluent is involved.",
  },
  {
    q: "How should pens be stored?",
    a: "Store as directed on the pen label, away from heat and light. Standard laboratory practice is refrigeration and use within the window stated on the label.",
  },
  {
    q: "Do you provide a Certificate of Analysis?",
    a: "Yes. Third-party certificates are published on each product page under Lab reports, and collected on the Certificates of Analysis page — one per strength and lot, each opening the laboratory's own copy with a verification code you can check with the lab. We link to the certificate rather than quoting a purity figure from it. For a lot that isn't listed yet, email support@timechainpeptides.com with the product and lot number.",
  },
  {
    q: "How does paying with Bitcoin work?",
    a: "Choose Bitcoin at checkout and you'll be sent to a hosted payment page showing the amount and a payment address or Lightning invoice. Once the payment confirms, your order moves out of pending automatically and your order status page updates. You can return to that page any time using the link from your confirmation.",
  },
  {
    q: "Are there discounts for larger quantities?",
    a: "Yes — volume discounts apply per SKU and are shown as a pricing table on each product page, so you can see the per-pen price at each quantity break before adding to cart.",
  },
  {
    q: "Where are your products compounded and tested?",
    a: "Raw peptide material originates overseas, as it does for effectively every supplier in this market. What differs is the rest of the chain: our products are compounded, tested, and verified in the United States rather than only being imported and resold.",
  },
];
