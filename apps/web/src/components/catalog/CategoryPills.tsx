import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { STOREFRONT_CATEGORIES, inCategory, type StorefrontCategory } from "@/lib/categories";
import styles from "./CategoryPills.module.css";

// One row of pill links above the catalog grid: "All categories" plus
// every group from lib/categories.ts with its live count. Plain links
// (not a client component): each one is the same page with ?category=
// set, so the grid re-renders server-side and sort/search survive.
// Counts come from the catalog as narrowed by the Pens | Vials toggle
// (`form`, carried in every link so the two filters compose), and never
// change as you click through categories. The active group's description
// shows beneath the row. Shown for both lines (David, 2026-10-22).
export default function CategoryPills({
  products,
  active,
  basePath,
  sort,
  query,
  form,
}: {
  products: ProductSummary[];
  active?: StorefrontCategory;
  basePath: string;
  sort: string;
  query?: string;
  form?: string;
}) {
  const href = (category?: StorefrontCategory) => {
    const params = new URLSearchParams();
    if (form) params.set("form", form);
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
