import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { groupByCategory } from "@/lib/categories";
import { promotableOnly } from "@/lib/compliance";
import { AUDIENCE, BOOKING_HREF, BOOKING_TARGET } from "@/lib/site";
import styles from "./Hero.module.css";

// Hero (2026-10-23): a plain statement on the left and, on the right, the
// catalog's categories as tiles with counts and two example compounds
// each, so "what's here" is answered before anyone scrolls. Examples are
// the first promotable members alphabetically, never a curated pick and
// never a GLP-class code name (lib/compliance.ts). Each tile opens the
// catalog narrowed to that category.
export default function Hero({ products, configurations }: { products: ProductSummary[]; configurations: number }) {
  const groups = groupByCategory(products).filter((group) => group.category.slug !== "supplies");

  return (
    <section className={styles.hero}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <span className="eyebrow">Research peptides, supplied in quantity</span>
          <h1 className={styles.headline}>
            Everything we supply, <em>in one place.</em>
          </h1>
          <p className={styles.lede}>
            Research peptides in pre-filled auto-injector pens and lyophilized vials for {AUDIENCE}. Review the
            catalog below, then book a call and we go through formats, strengths, quantities, documentation and
            pricing for your practice.
          </p>
          <div className={styles.actions}>
            <a href={BOOKING_HREF} {...BOOKING_TARGET} className="button buttonAccent">
              Book a meeting
            </a>
            <Link href="/shop" className="button buttonAccentOutline">
              Open the catalog
            </Link>
          </div>
          {products.length > 0 && (
            <p className={styles.meta}>
              {products.length} compounds · {configurations} format and strength configurations · pens and vials
            </p>
          )}
        </div>

        {groups.length > 0 && (
          <ul className={styles.tiles} aria-label="Catalog categories">
            {groups.map((group) => {
              const examples = promotableOnly(group.products)
                .slice(0, 2)
                .map((product) => product.name);
              return (
                <li key={group.category.slug}>
                  <Link href={`/shop?category=${group.category.slug}`} className={styles.tile}>
                    <span className={styles.tileCount}>{group.products.length}</span>
                    <span className={styles.tileLabel}>{group.category.label}</span>
                    {examples.length > 0 && <span className={styles.tileExamples}>{examples.join(", ")}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
