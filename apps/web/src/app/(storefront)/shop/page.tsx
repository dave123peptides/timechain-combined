import CatalogGrid from "@/components/catalog/CatalogGrid";
import { isSort } from "@/components/catalog/sort";
import PageBanner from "@/components/PageBanner";
import { listProductsOrEmpty } from "@/lib/api";

export const dynamic = "force-dynamic";

// Cut-out pen renders (see public/products/hero/README.md) of promotable,
// non-GLP products only (lib/compliance.ts) — this is a promotional
// surface.
const BANNER_PENS = ["/products/hero/tb-500.png", "/products/hero/bpc-157.png", "/products/hero/ghk-cu.png"];

// One flat, alphabetical catalog — deliberately no category filter or
// grouping (BioLongevity pattern). Benefit-named categories ("GLP-1 &
// Metabolic", "Sexual Health & Hormonal") are implied-intended-use claims
// incompatible with the RUO positioning, so Product.category never
// renders to customers; it stays internal-only. A stray ?category= from
// an old link is simply ignored.
//
// No format filter either: every sellable variant is form="pen"
// (ProductVariant._validate_is_sellable rejects every other form), so a
// format control would be a one-option filter that does nothing. The
// grid's standing line says the same thing more usefully. The Core
// reference's price/category/stock chips are likewise absent: categories
// are banned, and there is no stock state in the catalog.
export default async function ShopPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; sort?: string }>;
}) {
  const params = await searchParams;
  const query = params.q?.trim() || undefined;
  const sort = isSort(params.sort) ? params.sort : "name";

  // Degrades to empty rather than crashing the page if the API is
  // unreachable.
  const products = await listProductsOrEmpty({ q: query, sort });

  return (
    <main>
      <PageBanner
        variant="dark"
        eyebrow="Research use only"
        title={query ? `Results for “${query}”` : "Research Peptides For Sale"}
        images={BANNER_PENS}
      >
        {/* TODO(David): confirm the compounding/testing claim for the pen line before launch. */}
        <p>Pre-filled 3 mL auto-injector pens. Ready to use — no reconstitution.</p>
      </PageBanner>
      <CatalogGrid
        products={products}
        title={query ? "Search results" : "The Collection"}
        basePath="/shop"
        sort={sort}
        query={query}
      />
    </main>
  );
}
