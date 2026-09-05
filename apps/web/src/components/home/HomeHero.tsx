import Link from "next/link";
import SectionIcon from "@/components/SectionIcon";
import styles from "./HomeHero.module.css";

// Core-reference hero (David, 9/4): a calm uppercase headline with only
// its last line bold, one accent pill, and two vials floating on a plain
// light ground with three small callout badges. (The reference's
// honeycomb lattice was tried and parked at David's request — see
// components/HexLattice.tsx, currently unused.) Real claims only —
// every line below is verifiable in this codebase or confirmed by David:
// US compounding/testing (about page), lyophilized-only (enforced by
// ProductVariant._validate_is_sellable), third-party certificates
// (product_coas, published per lot on the PDP). Nothing about purity,
// delivery speed or free shipping — none of those are facts we hold.
//
// The vials are hard-coded, promotable products (lib/compliance.ts): a
// GLP-class code-name product must never appear here. Cut-out renders
// (transparent background) — see public/products/hero/README.md.
const HERO_VIALS = { front: "/products/hero/bpc-157.png", back: "/products/hero/tb-500.png" };

const BADGES = [
  { icon: "shield", label: "3rd-party tested" },
  { icon: "vial", label: "Lyophilized vials" },
  { icon: "flag", label: "US compounded & tested" },
] as const;

export default function HomeHero() {
  return (
    <section className={styles.hero}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <h1 className={styles.headline}>
            Research peptides,
            <br />
            compounded &amp; tested in the USA,
            <br />
            <strong>with third-party lab certificates</strong>
          </h1>
          <Link href="/shop" className={`button buttonPill ${styles.cta}`}>
            Shop Peptides
          </Link>
        </div>

        <div className={styles.visual} aria-hidden="true">
          <div className={styles.stage}>
            <span className={styles.shadow} />
            {/* eslint-disable-next-line @next/next/no-img-element -- product renders are static files under public/products */}
            <img src={HERO_VIALS.back} alt="" width={396} height={815} className={`${styles.vial} ${styles.vialBack}`} />
            {/* eslint-disable-next-line @next/next/no-img-element -- see above */}
            <img src={HERO_VIALS.front} alt="" width={394} height={815} className={`${styles.vial} ${styles.vialFront}`} />
          </div>
          {/* A sibling of the stage, not a child: overlaid on it on desktop,
              flowing beneath it on narrow viewports. */}
          <ul className={styles.badges}>
            {BADGES.map((badge, index) => (
              <li key={badge.label} className={`${styles.badge} ${styles[`badge${index}`]}`}>
                <SectionIcon name={badge.icon} size={13} />
                {badge.label}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
