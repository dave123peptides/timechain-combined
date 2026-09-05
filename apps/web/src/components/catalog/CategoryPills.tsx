import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { STOREFRONT_CATEGORIES, inCategory, type StorefrontCategory } from "@/lib/categories";
import styles from "./CategoryPills.module.css";

// One row of pill links above the catalog grid: "All categories" plus
// every group from lib/categories.ts with its live count. Plain links
// (not a client component): each one is the same page with ?category=
// set, so the grid re-renders server-side and sort/search survive.
// Counts come from the unfiltered catalog so they never change as you
// click through. The active group's description shows beneath the row.
export default function CategoryPills({
  products,
  active,
  basePath,
  sort,
  query,
}: {
  products: ProductSummary[];
  active?: StorefrontCategory;
  basePath: string;
  sort: string;
  query?: string;
}) {
  const href = (category?: StorefrontCategory) => {
    const params = new URLSearchParams();
    if (category) params.set("category", category.slug);
    if (sort !== "name") params.set("sort", sort);
    if (query) params.set("q", query);
    const qs = params.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  };

  return (
    <nav className={styles.wrap} aria-label="Product categories">
      <ul className={styles.list}>
        <li>
          <Link href={href()} className={`${styles.pill} ${active ? "" : styles.pillActive}`} aria-current={active ? undefined : "page"}>
            All categories
          </Link>
        </li>
        {STOREFRONT_CATEGORIES.map((category) => {
          const count = inCategory(products, category).length;
          const isActive = active?.slug === category.slug;
          return (
            <li key={category.slug}>
              <Link
                href={href(category)}
                className={`${styles.pill} ${isActive ? styles.pillActive : ""}`}
                aria-current={isActive ? "page" : undefined}
              >
                {category.label}
                <span className={styles.count}>{count}</span>
              </Link>
            </li>
          );
        })}
      </ul>
      {active && <p className={styles.description}>{active.description}</p>}
    </nav>
  );
}
