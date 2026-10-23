import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { formatMoney, formatStrength } from "@/lib/api";
import { formSingular, formsIn, strengthList, type FormKey } from "@/lib/forms";
import { PRICING_VISIBLE } from "@/lib/site";
import ProductImagePlaceholder from "./ProductImagePlaceholder";
import styles from "./ProductCard.module.css";

// Catalog card (2026-10-23): the compound first, and nothing to do but
// look. A generous image area, the name, its chemistry line, one quiet
// line of facts (formats and strengths) and a details link; the whole
// card opens the product page. No button: the site's one action is the
// Book a meeting link in the header (David, 2026-10-23). No price unless
// pricing is on (lib/site.ts) and the API sent one.
export default function ProductCard({ product, form }: { product: ProductSummary; form?: FormKey }) {
  const image = product.images[0];
  const href = `/shop/${product.slug}${form ? `?form=${form}` : ""}`;
  const forms = formsIn(product.variants);
  const strengths = strengthList(product.variants);
  const showPrice = PRICING_VISIBLE && product.starting_price_cents !== null;

  return (
    <article className={styles.card}>
      <Link href={href} className={styles.media} aria-label={product.name}>
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element -- product images are static files under public/products
          <img src={image} alt={product.name} className={`${styles.image} productPhoto`} loading="lazy" decoding="async" />
        ) : (
          <ProductImagePlaceholder name={product.name} />
        )}
        <span className={styles.formats} aria-hidden="true">
          {forms.map((f) => (
            <span key={f.key} className={styles.format}>
              {f.singular}
            </span>
          ))}
        </span>
      </Link>
      <div className={styles.body}>
        <Link href={href} className={styles.name}>
          {product.name}
        </Link>
        {product.description && <p className={styles.subtitle}>{product.description}</p>}
        <p className={styles.meta}>
          <span>{forms.map((f) => formSingular(f.key)).join(" · ")}</span>
          {strengths.length > 0 && <span>{strengths.map(formatStrength).join(", ")}</span>}
          {showPrice && <span>From {formatMoney(product.starting_price_cents as number)}</span>}
        </p>
        <Link href={href} className={styles.details}>
          Details
        </Link>
      </div>
    </article>
  );
}
