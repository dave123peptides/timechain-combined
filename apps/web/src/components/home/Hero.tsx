import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { formatStrength } from "@/lib/api";
import { promotableOnly } from "@/lib/compliance";
import { formSingular, formsIn, strengthList } from "@/lib/forms";
import { AUDIENCE } from "@/lib/site";
import styles from "./Hero.module.css";

// Hero (modern, minimal, 2026-10-22): a plain statement on the left and,
// instead of product photography, a live slice of the catalog sheet on
// the right: the first rows of the same list the page scrolls into. The
// slice is the alphabetical head of the promotable catalog, never a
// curated pick and never a GLP-class code name (lib/compliance.ts).
const PREVIEW_ROWS = 5;

export default function Hero({ products, configurations }: { products: ProductSummary[]; configurations: number }) {
  const preview = promotableOnly(products).slice(0, PREVIEW_ROWS);

  return (
    <section className={styles.hero}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <span className="eyebrow">Research peptides, supplied in quantity</span>
          <h1 className={styles.headline}>
            Everything we supply, <em>in one place.</em>
          </h1>
          <p className={styles.lede}>
            Research peptides in pre-filled auto-injector pens and lyophilized vials for {AUDIENCE}. See the whole
            catalog, pick formats, strengths and quantities, and send one order request.
          </p>
          <div className={styles.actions}>
            <Link href="/shop" className="button buttonAccent">
              Open the catalog
            </Link>
            <Link href="#how-it-works" className="button buttonAccentOutline">
              How ordering works
            </Link>
          </div>
          {products.length > 0 && (
            <p className={styles.meta}>
              {products.length} compounds · {configurations} format and strength configurations · pens and vials
            </p>
          )}
        </div>

        {preview.length > 0 && (
          <div className={styles.sheet} aria-label="Catalog preview">
            <div className={styles.sheetHead}>
              <span>Compound</span>
              <span>Formats</span>
              <span>Strengths</span>
            </div>
            <ul className={styles.rows}>
              {preview.map((product) => (
                <li key={product.slug}>
                  <Link href={`/shop/${product.slug}`} className={styles.row}>
                    <span className={styles.rowName}>{product.name}</span>
                    <span className={styles.rowFormats}>
                      {formsIn(product.variants).map((form) => (
                        <span key={form.key} className={styles.badge}>
                          {formSingular(form.key)}
                        </span>
                      ))}
                    </span>
                    <span className={styles.rowStrengths}>{strengthList(product.variants).map(formatStrength).join(", ")}</span>
                  </Link>
                </li>
              ))}
            </ul>
            <Link href="/shop" className={styles.sheetMore}>
              See all {products.length} compounds
            </Link>
          </div>
        )}
      </div>
    </section>
  );
}
