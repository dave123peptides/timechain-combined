import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { formatMoney, formatStrength } from "@/lib/api";
import { formSingular, formsIn, strengthList, type FormKey } from "@/lib/forms";
import { PRICING_VISIBLE } from "@/lib/site";
import ProductCardAddButton from "./ProductCardAddButton";
import ProductImagePlaceholder from "./ProductImagePlaceholder";
import styles from "./ProductCard.module.css";

// Catalog tile (B2B redesign, 2026-10-22): a framed card on the paper
// with the product on a soft ground, the name in the serif, the chemistry
// line beneath, then the facts a practice scans for: the formats it ships
// in and the strengths offered. No price unless pricing is on
// (lib/site.ts) and the API sent one. The card is an <article> with two
// links into the PDP (image, name) and the request button; when the grid
// is narrowed to one format the links carry ?form= so the product page
// opens on it.
export default function ProductCard({ product, form }: { product: ProductSummary; form?: FormKey }) {
  const image = product.images[0];
  const hoverImage = product.images[1];
  const href = `/shop/${product.slug}${form ? `?form=${form}` : ""}`;
  const forms = formsIn(product.variants);
  const strengths = strengthList(product.variants);
  const showPrice = PRICING_VISIBLE && product.starting_price_cents !== null;

  return (
    <article className={styles.card}>
      <Link href={href} className={styles.media} aria-label={product.name}>
        {image ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element -- product images are static files under public/products */}
            <img src={image} alt={product.name} className={`${styles.image} productPhoto`} loading="lazy" decoding="async" />
            {hoverImage && (
              // eslint-disable-next-line @next/next/no-img-element -- see above
              <img src={hoverImage} alt="" aria-hidden="true" className={`${styles.imageHover} productPhoto`} loading="lazy" decoding="async" />
            )}
          </>
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
        {/* No badges on cards (David, 9/5). Never add "Best Seller" or
            "Popular" here: fabricated demand signals. */}
      </Link>
      <div className={styles.body}>
        <Link href={href} className={styles.name}>
          {product.name}
        </Link>
        {product.description && <p className={styles.subtitle}>{product.description}</p>}
        <dl className={styles.facts}>
          <div>
            <dt>Format</dt>
            <dd>{forms.map((f) => formSingular(f.key)).join(" · ")}</dd>
          </div>
          {strengths.length > 0 && (
            <div>
              <dt>Strength</dt>
              <dd>{strengths.map(formatStrength).join(", ")}</dd>
            </div>
          )}
          {showPrice && (
            <div>
              <dt>From</dt>
              <dd>{formatMoney(product.starting_price_cents as number)}</dd>
            </div>
          )}
        </dl>
        <ProductCardAddButton slug={product.slug} variants={product.variants} href={href} />
      </div>
    </article>
  );
}
