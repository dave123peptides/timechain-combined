import Link from "next/link";
import type { ProductSort, ProductSummary } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import ShopSort from "./ShopSort";
import styles from "./CatalogGrid.module.css";

// The full catalog as one borderless 4-across grid with a result count
// and a sort control (Core reference, 9/4). Rendered by the homepage AND
// /shop — the same flat, alphabetical, category-free catalog in both
// places (see (storefront)/layout.tsx for why there is no category
// grouping). Supplies are already filtered out by the caller
// (lib/supplies.ts).
export default function CatalogGrid({
  products,
  title,
  basePath,
  sort,
  query,
}: {
  products: ProductSummary[];
  title: string;
  basePath: string;
  sort: ProductSort;
  query?: string;
}) {
  return (
    <section className={styles.section}>
      <div className="container">
        <h2 className={styles.title}>{title}</h2>

        <div className={styles.toolbar}>
          <p className={styles.count}>
            {query
              ? `${products.length} ${products.length === 1 ? "result" : "results"} for “${query}”`
              : `Showing all ${products.length} results`}
            {/* Stands in for a format filter: with a single format in the
                catalog, stating it is more useful than filtering on it. */}
            <span className={styles.note}> · Every product ships as a 3 mL auto-injector pen.</span>
          </p>
          <ShopSort value={sort} basePath={basePath} />
        </div>

        {products.length === 0 ? (
          <p className={styles.empty}>
            {query ? (
              <>
                Nothing matches that search.{" "}
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
            {products.map((product) => (
              <ProductCard key={product.slug} product={product} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
