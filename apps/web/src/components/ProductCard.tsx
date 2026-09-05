import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { formatMoney } from "@/lib/api";
import ProductCardAddButton from "./ProductCardAddButton";
import ProductImagePlaceholder from "./ProductImagePlaceholder";
import styles from "./ProductCard.module.css";

// The whole card used to be a single <Link>. It can't stay that way now
// that there's an Add to Cart button on it: a <button> inside an <a> is
// invalid nesting, React warns about it, and the two click targets fight
// each other. So the card is an <article> and the image and title are
// separate links into the same PDP.
export default function ProductCard({ product }: { product: ProductSummary }) {
  const image = product.images[0];
  const hoverImage = product.images[1];

  return (
    <article className={styles.card}>
      <Link href={`/shop/${product.slug}`} className={styles.media} aria-label={product.name}>
        {image ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element -- product images are arbitrary external URLs from Product.images */}
            <img src={image} alt={product.name} className={styles.image} loading="lazy" decoding="async" />
            {/* Only rendered when a second image exists (17 of 32 products
                today), so the grid doesn't double its image requests for
                products that have nothing to swap to. */}
            {hoverImage && (
              // eslint-disable-next-line @next/next/no-img-element -- see above
              <img src={hoverImage} alt="" aria-hidden="true" className={styles.imageHover} loading="lazy" decoding="async" />
            )}
          </>
        ) : (
          <ProductImagePlaceholder name={product.name} />
        )}
        {/* No badges on cards (David, 9/5 — the COA pill is gone too). Never
            add "Best Seller" / "Popular" here: fabricated demand signals.
            Certificates are on the product page and /coa. */}
      </Link>
      <div className={styles.body}>
        <Link href={`/shop/${product.slug}`} className={styles.name}>
          {product.name}
        </Link>
        <div className={styles.priceRow}>
          {product.variants.length > 1 && <span className={styles.from}>From</span>}
          <span className={styles.price}>{formatMoney(product.starting_price_cents)}</span>
        </div>
        <ProductCardAddButton slug={product.slug} variants={product.variants} />
      </div>
    </article>
  );
}
