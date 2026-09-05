import Link from "next/link";
import type { ProductSummary } from "@/lib/api";
import { formatMoney } from "@/lib/api";
import ProductCardAddButton from "@/components/ProductCardAddButton";
import ProductImagePlaceholder from "@/components/ProductImagePlaceholder";
import styles from "./sections.module.css";

// The americanpeptides-style essentials block: BAC water left the catalog
// grids (see lib/supplies.ts), and this one-click card on every compound
// PDP is where it sells instead. No checkbox-and-total machinery — with a
// single essential, a plain Add to Cart is the same click with less
// chrome. No "REQUIRED" badge either: the sentence states the fact, the
// badge would be pressure styling.
//
// Deliberately the letter placeholder, not supply.images[0]: BAC water's
// stored image is the borrowed BPC-157 placeholder photo, and a vial
// labeled BPC-157 next to "BAC Water" would misidentify the product.
// Switch to the real image once BAC water has its own photography.
export default function ReconstitutionAddon({ supply }: { supply: ProductSummary | undefined }) {
  if (!supply || supply.variants.length === 0) return null;

  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <span className="eyebrow">Reconstitution</span>
        <h2>Complete Your Protocol</h2>
      </div>
      <p className={styles.addonLead}>
        Lyophilized peptides require bacteriostatic water to reconstitute. Add it to your order in one click.
      </p>
      <div className={styles.addonCard}>
        <div className={styles.addonMedia}>
          <ProductImagePlaceholder name={supply.name} />
        </div>
        <div className={styles.addonInfo}>
          <Link href={`/shop/${supply.slug}`} className={styles.addonName}>
            {supply.name}
          </Link>
          <span className={styles.addonMeta}>
            {supply.variants[0].strength} &middot; {formatMoney(supply.starting_price_cents)}
          </span>
        </div>
        <div className={styles.addonAction}>
          <ProductCardAddButton slug={supply.slug} variants={supply.variants} />
        </div>
      </div>
    </section>
  );
}
