import CatalogGrid from "@/components/catalog/CatalogGrid";
import { isSort } from "@/components/catalog/sort";
import { isView } from "@/components/catalog/view";
import PageBanner from "@/components/PageBanner";
import { listProductsOrEmpty } from "@/lib/api";
import { findCategory } from "@/lib/categories";
import { findForm } from "@/lib/forms";

export const dynamic = "force-dynamic";

// The catalog page: the same order sheet as the homepage, under its own
// heading. ?form= narrows to one line, ?category= within it, ?view=
// switches sheet and grid; an unknown value means "all" / the default.
// Product.category (the internal taxonomy) still never renders.
export default async function ShopPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; sort?: string; category?: string; form?: string; view?: string }>;
}) {
  const params = await searchParams;
  const query = params.q?.trim() || undefined;
  const sort = isSort(params.sort) ? params.sort : "name";
  const category = findCategory(params.category);
  const form = findForm(params.form);
  const view = isView(params.view) ? params.view : "list";

  const products = await listProductsOrEmpty({ q: query, sort });

  return (
    <main>
      <PageBanner eyebrow="Research use only" title={query ? `Results for “${query}”` : form ? `Research peptide ${form.label.toLowerCase()}` : "Catalog"}>
        <p>
          {form
            ? form.description
            : "Pre-filled auto-injector pens and lyophilized vials. Pick a format, narrow by category, and add what you need to your order request."}
        </p>
      </PageBanner>
      <CatalogGrid
        products={products}
        title={query ? "Search results" : "Every compound"}
        basePath="/shop"
        sort={sort}
        query={query}
        category={category}
        form={form}
        view={view}
      />
    </main>
  );
}
