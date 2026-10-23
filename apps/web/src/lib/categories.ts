import type { ProductSummary } from "@/lib/api";

// Customer-facing benefit categories (David, 2026-09-05), taken from his
// TCP Guide (https://tcpguidehelp.vercel.app/): the seven groups, their
// one-line descriptions, and which compounds sit in each. A compound can
// belong to more than one group, which is why this is a presentation-
// layer list of slugs rather than the single internal Product.category.
// Groups are by compound, so they apply to a product's pen and vial
// variants alike; the Pens | Vials toggle narrows first, then these.
//
// TODO(attorney-review): the vial site deliberately never rendered
// categories because benefit-named groups ("Weight Loss", "Anti-Aging",
// "Sexual Health") read as intended-use claims, see
// docs/plans/claude-answers-glp-decision.md ("NEVER reference weight
// loss, appetite ..."). David chose to show them on the pens site and,
// on 2026-10-22, on both lines of the combined site; the labels and
// descriptions below are his guide's wording, verbatim.
//
// Not in the guide, placed by compound class: cjc-1295-no-dac, hexarelin,
// ghrp-2 and ghrp-6 (GH secretagogues, growth), hcg-6000-units and mt-1
// (reproductive hormone / melanocortin, sexual), aod-9604 (hGH fragment
// studied in lipid metabolism, weight), ghk-cu-kpv (healing). BAC water
// is a supply (lib/supplies.ts) and belongs to no group.
export type StorefrontCategory = {
  slug: string;
  label: string;
  description: string;
  products: string[];
};

export const STOREFRONT_CATEGORIES: StorefrontCategory[] = [
  {
    slug: "weight",
    label: "Weight Loss, Appetite & Metabolic Health",
    description:
      "Compounds working through GLP-1/GIP/glucagon pathways, amylin, or mitochondrial signaling for fat loss, blood sugar control, and energy.",
    products: ["glp-1s", "glp-2t", "glp-3r", "cagrilinitide", "mots-c", "5-amino-1mq", "aod-9604"],
  },
  {
    slug: "healing",
    label: "Tissue Repair, Healing & Recovery",
    description:
      "The classic regenerative compounds for injuries, joints, tendons, gut lining, and soft tissue.",
    products: [
      "bpc-157",
      "tb-500",
      "bpc-157-tb-500-wolverine",
      "ghk-cu",
      "glow-bpc-157-tb-500-ghk",
      "klow-kpv-bpc-157-tb-500-ghk",
      "kpv",
      "ghk-cu-kpv",
    ],
  },
  {
    slug: "growth",
    label: "Growth Hormone, Muscle & Body Composition",
    description: "Stimulate your own GH or IGF-1 pathways for fat loss, recovery, and lean mass.",
    products: [
      "cjc-no-dac-ipamorelin",
      "cjc-1295-no-dac",
      "ipamorelin",
      "tesamorelin",
      "tesamorelin-ipamorelin",
      "sermorelin",
      "hexarelin",
      "igf1-lr3",
      "ghrp-2",
      "ghrp-6",
    ],
  },
  {
    slug: "cognitive",
    label: "Cognitive, Mood & Sleep",
    description: "Focus, memory, mood, stress resilience, and deeper sleep.",
    products: ["selank", "semax", "dihexa", "dsip", "epithalon"],
  },
  {
    slug: "sexual",
    label: "Sexual Health & Libido",
    description: "Desire, arousal, and reproductive hormone support for both men and women.",
    products: ["pt-141", "mt-2", "mt-1", "kisspeptin", "hcg-6000-units"],
  },
  {
    slug: "longevity",
    label: "Anti-Aging, Longevity & Cellular Health",
    description: "Cellular energy, antioxidant defense, and the pathways most tied to aging well.",
    products: ["mots-c", "5-amino-1mq", "ghk-cu", "glow-bpc-157-tb-500-ghk", "epithalon", "nad", "ss-31", "glutathione"],
  },
  {
    slug: "immunity",
    label: "Immune Support",
    description: "Immune modulation, antimicrobial defense, and inflammatory balance.",
    products: ["kpv", "glutathione", "ta-1", "ll-37"],
  },
];

export function findCategory(slug: string | undefined): StorefrontCategory | undefined {
  return STOREFRONT_CATEGORIES.find((category) => category.slug === slug);
}

/** Validates a ?category= query value; anything unknown means "all". */
export function isCategorySlug(value: string | undefined): value is string {
  return findCategory(value) !== undefined;
}

export function inCategory<T extends Pick<ProductSummary, "slug">>(products: T[], category: StorefrontCategory): T[] {
  return products.filter((product) => category.products.includes(product.slug));
}

// The catalog grouped for display (2026-10-23, David: "make it a little
// more easy to see the different peptides"): each product under the FIRST
// group that lists it, in STOREFRONT_CATEGORIES order, and anything no
// group lists (BAC water) under a closing "Supplies" group. Presentation
// only; the pills still filter on the full membership (a compound can be
// in two groups).
export const OTHER_CATEGORY: StorefrontCategory = {
  slug: "supplies",
  label: "Supplies",
  description: "Reconstitution supplies for the lyophilized vials.",
  products: [],
};

export type CategoryGroup = { category: StorefrontCategory; products: ProductSummary[] };

export function groupByCategory<T extends ProductSummary>(products: T[]): { category: StorefrontCategory; products: T[] }[] {
  const placed = new Set<string>();
  const groups = STOREFRONT_CATEGORIES.map((category) => {
    const members = products.filter((product) => !placed.has(product.slug) && category.products.includes(product.slug));
    for (const product of members) placed.add(product.slug);
    return { category, products: members };
  }).filter((group) => group.products.length > 0);
  const rest = products.filter((product) => !placed.has(product.slug));
  if (rest.length > 0) groups.push({ category: OTHER_CATEGORY, products: rest });
  return groups;
}
