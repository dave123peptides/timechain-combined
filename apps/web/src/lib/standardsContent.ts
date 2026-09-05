// Single source of truth for the quality/standards sections
// (ProofSection, CommitmentsGrid, VerificationPipeline — on /about since
// the 9/4 Core-reference redesign moved them off the homepage). Same
// pattern as SITE_FAQ: sections render from this module so the claims on
// different parts of the site can never disagree with each other.
//
// THE STANDING RULE APPLIES HERE MORE THAN ANYWHERE ELSE ON THE SITE.
// These sections are modeled on americanpeptides.com's quality sections
// (David's 9/2 reference screenshots), but their copy could NOT be reused:
// it claims per-batch USP sterility/endotoxin/ICP-MS testing, a named
// third-party lab, an average purity figure, FDA registration, and GMP
// facilities. None of that exists for TimeChain (see the about page's
// docstring for the claims that were already removed once). Every entry
// below is either verifiable in this codebase or a fact David has
// confirmed (about page / TrustBar / SITE_FAQ). Do not add a stat or a
// testing claim here without the data to back it.

// ---------------------------------------------------------------------------
// ProofSection — "what a purity number doesn't tell you".
// These four cards are industry EDUCATION, not TimeChain claims: they
// describe what HPLC/MS methodology inherently cannot detect, which is
// factual chemistry. Deliberately absent: any "we test for this" line —
// the honest TimeChain position (about page) is documentation on request,
// never an implied test result.
// ---------------------------------------------------------------------------

export type PurityGap = {
  number: string;
  tag: string;
  title: string;
  sub: string;
  missesLabel: string;
  misses: string;
  mattersLabel: string;
  matters: string;
};

export const PURITY_GAPS: PurityGap[] = [
  {
    number: "01",
    tag: "Endotoxins",
    title: "Toxic fragments left behind by dead bacteria.",
    sub: "Heat-stable. They survive standard sterilization.",
    missesLabel: "Why a purity number misses them",
    misses:
      "HPLC and mass spectrometry characterize chemistry. Endotoxins are biological residue — invisible to both. A vial can test 99% pure and still carry them.",
    mattersLabel: "Why it matters",
    matters:
      "Endotoxins are biologically active on their own. In sensitive research systems they confound results before an experiment even begins.",
  },
  {
    number: "02",
    tag: "Sterility",
    title: "Living microbial contamination.",
    sub: "Assessed by culture — never by a chromatogram.",
    missesLabel: "Why a purity number misses it",
    misses:
      "A purity test doesn't culture for bacteria, fungi, or yeast. Live contamination can grow in a vial whose purity figure looks flawless.",
    mattersLabel: "Why it matters",
    matters:
      "Microbial growth introduces uncontrolled variables into any research system — and no percentage on a label warns you it's there.",
  },
  {
    number: "03",
    tag: "Heavy metals",
    title: "Lead, arsenic, mercury, and cadmium from synthesis.",
    sub: "Inorganic. Detectable only by dedicated methods such as ICP-MS.",
    missesLabel: "Why a purity number misses them",
    misses:
      "Heavy metals are inorganic — HPLC and mass spec are blind to them entirely. Detecting them takes a separate analysis most of this market never runs.",
    mattersLabel: "Why it matters",
    matters:
      "Metal contamination accumulates in biological models and produces confounding effects in long-term studies.",
  },
  {
    number: "04",
    tag: "Batch consistency",
    title: "Whether this batch matches the last one.",
    sub: "A single number describes a single sample — not a supply chain.",
    missesLabel: "Why a purity number misses it",
    misses:
      "A purity figure is a snapshot of one vial at one point in time. It carries no information about the batch before it or the batch after it.",
    mattersLabel: "Why it matters",
    matters:
      "Reproducibility is the foundation of legitimate research. If batches drift, the data built on them drifts too.",
  },
];

// ---------------------------------------------------------------------------
// CommitmentsGrid — six commitments, each closed by a stat line. Every
// stat is true by construction or David-confirmed; several are enforced
// in code (see the inline notes).
// ---------------------------------------------------------------------------

export type IconName =
  | "flask"
  | "vial"
  | "flag"
  | "document"
  | "layers"
  | "bitcoin"
  | "link"
  | "shield"
  | "record"
  | "gate"
  | "loop"
  | "map"
  | "chat"
  // Chrome glyphs (header, drawer, contact) — see SectionIcon.
  | "search"
  | "bag"
  | "menu"
  | "close"
  | "mail"
  | "trash"
  | "chevronLeft"
  | "check"
  | "warning"
  | "copy"
  | "external";

export type Commitment = {
  icon: IconName;
  number: string;
  title: string;
  body: string;
  stat: string;
  statLabel: string;
};

export const COMMITMENTS: Commitment[] = [
  {
    icon: "flask",
    number: "01",
    title: "Verified Sourcing",
    // Enforced: a product with no confirmed supplier mapping cannot be
    // made sellable (see the about page's "What verified means here").
    body: "Every listed compound is matched and confirmed against supplier records before it can be offered — enforced in our systems, not stated as policy.",
    stat: "100%",
    statLabel: "of listed products supplier-mapped",
  },
  {
    icon: "vial",
    number: "02",
    title: "Lyophilized Only",
    // Enforced: ProductVariant._validate_is_sellable rejects every other
    // form outright.
    body: "Everything here ships as a freeze-dried vial. Pens and pre-constituted formats can't even be entered into the catalog.",
    stat: "100%",
    statLabel: "lyophilized vials · enforced in code",
  },
  {
    icon: "flag",
    number: "03",
    title: "US Chain of Custody",
    body: "Raw material in this industry originates overseas — for everyone. What differs is what happens next: our chain stays domestic from there.",
    stat: "USA",
    statLabel: "compounded · tested · verified",
  },
  {
    icon: "document",
    number: "04",
    title: "Certificates Published",
    // Real: product_coas holds the lab's certificates per lot; the PDP's
    // Lab reports tab and /coa render them. Still no purity number
    // anywhere — the certificate carries its own, in context.
    body: "Third-party Certificates of Analysis are published per lot on each product page — each listing the assays it covers and carrying the laboratory's verification code. We link to the lab's copy rather than quoting a number from it.",
    stat: "Per lot",
    statLabel: "third-party COA · verifiable with the lab",
  },
  {
    // Volume pricing moved to its own band (VolumeBand renders the real
    // tier schedule from the API), freeing this slot for the support
    // claim the contact page already commits to: email reaches a person,
    // not a queue. No response-time promise — none is confirmed.
    icon: "chat",
    number: "05",
    title: "Direct Support",
    body: "Email reaches a person, not a ticket queue — questions about specifications, documentation, and orders answered by the people who run the catalog.",
    stat: "One inbox",
    statLabel: "support@timechainpeptides.com",
  },
  {
    icon: "bitcoin",
    number: "06",
    title: "Bitcoin at Checkout",
    body: "Pay on-chain or over Lightning through a hosted payment page. Orders move out of pending automatically once the payment confirms.",
    stat: "BTC",
    statLabel: "on-chain & Lightning accepted",
  },
];

// The strip under the grid. Where americanpeptides shows "VERIFIED BY"
// third-party badges (a lab, GMP, FDA registration), we have no third
// parties to cite — what we actually have is stronger to our story and
// weaker to fake: constraints enforced by our own systems.
export type EnforcementItem = {
  value: string;
  label: string;
};

export const ENFORCEMENT_STRIP: EnforcementItem[] = [
  { value: "Supplier mapping", label: "required before listing" },
  { value: "Lyophilized-only", label: "catalog validator" },
  { value: "Auto-delist", label: "on supplier record changes" },
  { value: "RUO acknowledgment", label: "required at checkout" },
];

// ---------------------------------------------------------------------------
// VerificationPipeline — the gate a product clears before it can be sold.
// This is the honest counterpart to americanpeptides' "18 days of
// scrutiny" testing wall: we cannot describe a testing program we don't
// run, but the listing gate below is real and mostly machine-enforced.
// Order mirrors the actual flow: gate, match, compound, test, record,
// format, monitor.
// ---------------------------------------------------------------------------

export type PipelineStep = {
  number: string;
  icon: IconName;
  title: string;
  body: string;
  // Exactly one step carries the highlight treatment (the big stat card).
  highlight?: {
    stat: string;
    statLabel: string;
  };
};

export const PIPELINE_STEPS: PipelineStep[] = [
  {
    number: "01",
    icon: "gate",
    title: "The Listing Gate",
    highlight: {
      stat: "0",
      statLabel: "ways to list an unverified product",
    },
    body: "A product with no confirmed supplier mapping cannot be made available for sale. That's a validator in the catalog system, not a policy memo — there is no override.",
  },
  {
    number: "02",
    icon: "link",
    title: "Supplier Record Match",
    body: "Every compound is matched and confirmed against the supplier's own records — identity, batch, and mapping — before it's considered for the catalog.",
  },
  {
    number: "03",
    icon: "flask",
    title: "US Compounding",
    body: "Raw material originates overseas, as it does industry-wide. Compounding happens in the United States — the chain stays domestic from arrival on.",
  },
  {
    number: "04",
    icon: "shield",
    title: "US Testing",
    body: "Tested in the United States before listing. The certificate for each lot is published on the product page and verifiable with the laboratory — we link to the document rather than quoting figures from it.",
  },
  {
    number: "05",
    icon: "record",
    title: "Documented Handling",
    body: "Batch and mapping records are kept for every product from intake through shipment, start to finish.",
  },
  {
    number: "06",
    icon: "vial",
    title: "Format Gate",
    body: "The catalog rejects anything that isn't a lyophilized vial. Pens and pre-constituted formats fail validation and cannot be listed.",
  },
  {
    number: "07",
    icon: "loop",
    title: "Continuous Verification",
    body: "Verification doesn't stop at listing. If a supplier record changes or disappears, the affected products are pulled from sale automatically.",
  },
];
