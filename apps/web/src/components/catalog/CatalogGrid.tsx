import Link from "next/link";
import type { ProductSort, ProductSummary } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import { inCategory, type StorefrontCategory } from "@/lib/categories";
import CategoryPills from "./CategoryPills";
import ShopSort from "./ShopSort";
import styles from "./CatalogGrid.module.css";

// The full catalog as one borderless 4-across grid with a category pill
// row, a result count and a sort control (Core reference, 9/4; pills
// added for the pens site, David 2026-09-05). Rendered by the homepage
// AND /shop. `products` is the whole (search-filtered) catalog: the pill
// counts are taken from it, and `category` narrows what the grid shows.
export default function CatalogGrid({
  products,
  title,
  basePath,
  sort,
  query,
  category,
}: {
  products: ProductSummary[];
  title: string;
  basePath: string;
  sort: ProductSort;
  query?: string;
  category?: StorefrontCategory;
}) {
  const visible = category ? inCategory(products, category) : products;
  return (
    <section className={styles.section}>
      <div className="container">
        <h2 className={styles.title}>{title}</h2>

        <CategoryPills products={products} active={category} basePath={basePath} sort={sort} query={query} />

        <div className={styles.toolbar}>
          <p className={styles.count}>
            {query
              ? `${visible.length} ${visible.length === 1 ? "result" : "results"} for “${query}”`
              : category
                ? `Showing ${visible.length} ${visible.length === 1 ? "result" : "results"} in ${category.label}`
                : `Showing all ${visible.length} results`}
            {/* Stands in for a format filter: with a single format in the
                catalog, stating it is more useful than filtering on it. */}
            <span className={styles.note}> · Every product ships as a 3 mL auto-injector pen.</span>
          </p>
          <ShopSort value={sort} basePath={basePath} />
        </div>

        {visible.length === 0 ? (
          <p className={styles.empty}>
            {query || category ? (
              <>
                Nothing matches {query ? "that search" : "this category"}.{" "}
                <Link href={basePath} className={styles.emptyLink}>
                  View all products
                </Link>
                .
              </>
            ) : (
              "Nothing is available right now — check back soon."
            )}
          </p>
        ) : (
          <div className={styles.grid}>
            {visible.map((product) => (
              <ProductCard key={product.slug} product={product} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
