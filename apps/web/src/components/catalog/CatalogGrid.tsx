import Link from "next/link";
import type { ReactNode } from "react";
import type { ProductSort, ProductSummary } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import { groupByCategory, inCategory, type StorefrontCategory } from "@/lib/categories";
import { narrowToForm, type StorefrontForm } from "@/lib/forms";
import CatalogRow from "./CatalogRow";
import CategoryPills from "./CategoryPills";
import FormPills from "./FormPills";
import ShopSort from "./ShopSort";
import { DEFAULT_VIEW, VIEW_OPTIONS, type CatalogView } from "./view";
import styles from "./CatalogGrid.module.css";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

// The whole catalog (2026-10-23, David: "more easy to see the different
// peptides"). The default view is cards grouped under their category
// headings, so the page reads as "here is what we have", with one button
// per card. A category filter, a search or a format shows a flat grid of
// what matched. The dense order sheet (one row per compound with the
// controls in the row) is the other view. Rendered by the homepage AND
// /shop. `products` is the whole (search-filtered) catalog; `form`
// narrows to one line, `category` narrows within it.
export default function CatalogGrid({
  products,
  title,
  basePath,
  sort,
  query,
  category,
  form,
  view = DEFAULT_VIEW,
}: {
  products: ProductSummary[];
  title: ReactNode;
  basePath: string;
  sort: ProductSort;
  query?: string;
  category?: StorefrontCategory;
  form?: StorefrontForm;
  view?: CatalogView;
}) {
  const inForm = form ? narrowToForm(products, form) : products;
  const visible = category ? inCategory(inForm, category) : inForm;
  const unit = form ? [form.singular.toLowerCase(), form.label.toLowerCase()] : ["compound", "compounds"];
  const count = plural(visible.length, unit[0], unit[1]);
  const grouped = view === "cards" && !category && !query && sort === "name";

  const viewHref = (next: CatalogView) => {
    const params = new URLSearchParams();
    if (next !== DEFAULT_VIEW) params.set("view", next);
    if (form) params.set("form", form.key);
    if (category) params.set("category", category.slug);
    if (sort !== "name") params.set("sort", sort);
    if (query) params.set("q", query);
    const qs = params.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  };

  const cards = (items: ProductSummary[]) => (
    <div className={styles.grid}>
      {items.map((product) => (
        <ProductCard key={product.slug} product={product} form={form?.key} />
      ))}
    </div>
  );

  return (
    <section className={styles.section} id="catalog">
      <div className="container">
        <div className={styles.head}>
          <h2 className={styles.title}>{title}</h2>
          <FormPills products={products} active={form} basePath={basePath} sort={sort} query={query} category={category} />
        </div>
        <CategoryPills products={inForm} active={category} basePath={basePath} sort={sort} query={query} form={form?.key} />

        <div className={styles.toolbar}>
          <p className={styles.count}>
            {query ? `${count} for “${query}”` : category ? `${count} in ${category.label}` : `All ${count}`}
            <span className={styles.note}>
              {" · "}
              {form ? form.description : "Pens ship ready to use. Vials ship lyophilized and are reconstituted before use."}
            </span>
          </p>
          <div className={styles.tools}>
            <div className={styles.viewSwitch} role="group" aria-label="View">
              {VIEW_OPTIONS.map((option) => (
                <Link
                  key={option.value}
                  href={viewHref(option.value)}
                  className={`${styles.viewOption} ${option.value === view ? styles.viewOptionActive : ""}`}
                  aria-current={option.value === view ? "true" : undefined}
                >
                  {option.label}
                </Link>
              ))}
            </div>
            <ShopSort value={sort} basePath={basePath} />
          </div>
        </div>

        {visible.length === 0 ? (
          <p className={styles.empty}>
            {query || category || form ? (
              <>
                Nothing matches {query ? "that search" : category ? "this category" : "this format"}.{" "}
                <Link href={basePath} className={styles.emptyLink}>
                  View all compounds
                </Link>
                .
              </>
            ) : (
              "Nothing is available right now. Check back soon."
            )}
          </p>
        ) : view === "sheet" ? (
          <ul className={styles.sheet}>
            <li className={styles.sheetHead} aria-hidden="true">
              <span />
              <span>Compound</span>
              <span>Formats</span>
              <span className={styles.sheetHeadControls}>Configuration · quantity</span>
            </li>
            {visible.map((product) => (
              <CatalogRow key={product.slug} product={product} form={form?.key} />
            ))}
          </ul>
        ) : grouped ? (
          <div className={styles.groups}>
            {groupByCategory(visible).map((group) => (
              <section key={group.category.slug} id={`cat-${group.category.slug}`} className={styles.group}>
                <div className={styles.groupHead}>
                  <h3 className={styles.groupTitle}>
                    {group.category.label}
                    <span className={styles.groupCount}>{group.products.length}</span>
                  </h3>
                  {group.category.description && <p className={styles.groupDescription}>{group.category.description}</p>}
                </div>
                {cards(group.products)}
              </section>
            ))}
          </div>
        ) : (
          cards(visible)
        )}
      </div>
    </section>
  );
}
