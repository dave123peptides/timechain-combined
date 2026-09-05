import type { ProductSummary } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import styles from "./sections.module.css";

// "Related Products" (Core reference, 9/4) — the same source as the old
// "Pairs Well With": Product.content.pairs_with resolved against the live
// sellable catalog by the page, which also applies the promotable filter
// (lib/compliance.ts). Hidden when there is nothing to show; there is
// deliberately no "other products" fallback, which would be a curated
// suggestion surface.
export default function RelatedProducts({ products }: { products: ProductSummary[] }) {
  if (products.length === 0) return null;

  return (
    <section className={styles.section}>
      <h2 className={styles.relatedTitle}>Related Products</h2>
      <div className={styles.relatedGrid}>
        {products.map((product) => (
          <ProductCard key={product.slug} product={product} />
        ))}
      </div>
    </section>
  );
}
