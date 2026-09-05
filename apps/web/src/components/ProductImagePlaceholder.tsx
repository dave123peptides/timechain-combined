import styles from "./ProductImagePlaceholder.module.css";

// Shown wherever a product/variant has no real photo yet — every product
// does today (Product.images is external-URL-only with no committed
// asset pipeline; see docs/testing for the current catalog state). This
// is explicitly NOT a substitute for real photography — just a clean,
// on-brand placeholder instead of a broken-image icon in the interim.
export default function ProductImagePlaceholder({ name }: { name: string }) {
  return (
    <div className={styles.placeholder} aria-hidden="true">
      <span className={styles.mark}>{name.charAt(0).toUpperCase()}</span>
    </div>
  );
}
