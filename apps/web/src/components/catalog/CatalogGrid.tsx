import Link from "next/link";
import type { ProductSort, ProductSummary } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import { inCategory, type StorefrontCategory } from "@/lib/categories";
import { narrowToForm, type StorefrontForm } from "@/lib/forms";
import CategoryPills from "./CategoryPills";
import FormPills from "./FormPills";
import ShopSort from "./ShopSort";
import styles from "./CatalogGrid.module.css";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

// The full catalog as one borderless 4-across grid with the Pens | Vials
// toggle and a category pill row on top, a result count and a sort
// control (Core reference, 9/4; pills for the pens site, David
// 2026-09-05; the format toggle for the combined site, 2026-10-22).
// Rendered by the homepage AND /shop. `products` is the whole
// (search-filtered) catalog: the toggle's counts are taken from it,
// `form` narrows it to one line (variants of that form only, "From"
// price recomputed), and `category` narrows what is left. The category
// counts follow the form, so "Weight Loss 6" means six in the chosen
// format.
export default function CatalogGrid({
  products,
  title,
  basePath,
  sort,
  query,
  category,
  form,
}: {
  products: ProductSummary[];
  title: string;
  basePath: string;
  sort: ProductSort;
  query?: string;
  category?: StorefrontCategory;
  form?: StorefrontForm;
}) {
  const inForm = form ? narrowToForm(products, form) : products;
  const visible = category ? inCategory(inForm, category) : inForm;
  const unit = form ? [form.singular.toLowerCase(), form.label.toLowerCase()] : ["result", "results"];
  const count = plural(visible.length, unit[0], unit[1]);

  return (
    <section className={styles.section}>
      <div className="container">
        <h2 className={styles.title}>{title}</h2>

        <FormPills products={products} active={form} basePath={basePath} sort={sort} query={query} category={category} />
        <CategoryPills products={inForm} active={category} basePath={basePath} sort={sort} query={query} form={form?.key} />

        <div className={styles.toolbar}>
          <p className={styles.count}>
            {query ? `${count} for “${query}”` : category ? `Showing ${count} in ${category.label}` : `Showing all ${count}`}
            <span className={styles.note}>
              {" · "}
              {form
                ? form.description
                : "Pens ship ready to use. Vials ship lyophilized and are reconstituted before use."}
            </span>
          </p>
          <ShopSort value={sort} basePath={basePath} />
        </div>

        {visible.length === 0 ? (
          <p className={styles.empty}>
            {query || category || form ? (
              <>
                Nothing matches {query ? "that search" : category ? "this category" : "this format"}.{" "}
                <Link href={basePath} className={styles.emptyLink}>
                  View all products
                </Link>
                .
              </>
            ) : (
              "Nothing is available right now. Check back soon."
            )}
          </p>
        ) : (
          <div className={styles.grid}>
            {visible.map((product) => (
              <ProductCard key={product.slug} product={product} form={form?.key} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
