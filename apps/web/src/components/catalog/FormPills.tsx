import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import type { StorefrontCategory } from "@/lib/categories";
import { STOREFRONT_FORMS, narrowToForm, type StorefrontForm } from "@/lib/forms";
import styles from "./FormPills.module.css";

// The Pens | Vials toggle above the catalog grid (David, 2026-10-22): a
// segmented control of plain links, each the same page with ?form= set,
// so the grid re-renders server-side and category, sort and search all
// survive. Counts come from the unfiltered catalog so they never change
// as you click through. Rendered only when more than one form is for
// sale: a one-option toggle filters nothing.
export default function FormPills({
  products,
  active,
  basePath,
  sort,
  query,
  category,
}: {
  products: ProductSummary[];
  active?: StorefrontForm;
  basePath: string;
  sort: string;
  query?: string;
  category?: StorefrontCategory;
}) {
  const forms = STOREFRONT_FORMS.map((form) => ({ form, count: narrowToForm(products, form).length })).filter(
    (entry) => entry.count > 0
  );
  if (forms.length < 2) return null;

  const href = (form?: StorefrontForm) => {
    const params = new URLSearchParams();
    if (form) params.set("form", form.key);
    if (category) params.set("category", category.slug);
    if (sort !== "name") params.set("sort", sort);
    if (query) params.set("q", query);
    const qs = params.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  };

  return (
    <nav className={styles.wrap} aria-label="Product format">
      <ul className={styles.segments}>
        <li>
          <Link
            href={href()}
            className={`${styles.segment} ${active ? "" : styles.segmentActive}`}
            aria-current={active ? undefined : "page"}
          >
            All
            <span className={styles.count}>{products.length}</span>
          </Link>
        </li>
        {forms.map(({ form, count }) => {
          const isActive = active?.key === form.key;
          return (
            <li key={form.key}>
              <Link
                href={href(form)}
                className={`${styles.segment} ${isActive ? styles.segmentActive : ""}`}
                aria-current={isActive ? "page" : undefined}
              >
                {form.label}
                <span className={styles.count}>{count}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
