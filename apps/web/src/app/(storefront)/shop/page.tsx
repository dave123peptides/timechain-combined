import CatalogGrid from "@/components/catalog/CatalogGrid";
import { isSort } from "@/components/catalog/sort";
import PageBanner from "@/components/PageBanner";
import { listProductsOrEmpty } from "@/lib/api";
import { findCategory } from "@/lib/categories";
import { findForm } from "@/lib/forms";

export const dynamic = "force-dynamic";

// Cut-out pen renders (see public/products/hero/README.md) of promotable,
// non-GLP products only (lib/compliance.ts): this is a promotional
// surface. Shown on the all-products and Pens views; the Vials view has
// no vial render to match, so it goes without.
const BANNER_PENS = ["/products/hero/tb-500.png", "/products/hero/bpc-157.png", "/products/hero/ghk-cu.png"];

// One flat, alphabetical catalog with the Pens | Vials toggle
// (lib/forms.ts, David 2026-10-22) and a benefit-category pill row
// (lib/categories.ts) on top. ?form= narrows to one line, ?category=
// narrows within it; an unknown value for either means "all".
// Product.category (the internal taxonomy) still never renders.
export default async function ShopPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; sort?: string; category?: string; form?: string }>;
}) {
  const params = await searchParams;
  const query = params.q?.trim() || undefined;
  const sort = isSort(params.sort) ? params.sort : "name";
  const category = findCategory(params.category);
  const form = findForm(params.form);

  // Degrades to empty rather than crashing the page if the API is
  // unreachable.
  const products = await listProductsOrEmpty({ q: query, sort });

  const title = query ? `Results for “${query}”` : form ? `Research Peptide ${form.label}` : "Research Peptides For Sale";

  return (
    <main>
      <PageBanner
        variant="dark"
        eyebrow="Research use only"
        title={title}
        images={form?.key === "lyophilized" ? undefined : BANNER_PENS}
      >
        <p>
          {form
            ? form.description
            : "Pre-filled auto-injector pens and lyophilized vials. Pick a format, or browse the whole catalog."}
        </p>
      </PageBanner>
      <CatalogGrid
        products={products}
        title={query ? "Search results" : "The Collection"}
        basePath="/shop"
        sort={sort}
        query={query}
        category={category}
        form={form}
      />
    </main>
  );
}
