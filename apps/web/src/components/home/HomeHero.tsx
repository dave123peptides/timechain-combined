import Link from "next/link";
import SectionIcon from "@/components/SectionIcon";
import styles from "./HomeHero.module.css";

// Core-reference hero (David, 9/4), carried over to the pens site
// (2026-09-05): a calm uppercase headline with only its last line bold,
// one accent pill, and two pens floating on a plain light ground with
// three small callout badges. Real claims only — every line below is
// verifiable in this codebase or confirmed by David: pens-only (enforced
// by ProductVariant._validate_is_sellable), ready to use (a pre-filled
// pen needs no reconstitution). Nothing about purity, delivery speed,
// free shipping or third-party testing — none of those are facts this
// site holds yet.
//
// TODO(David): the bold closing line is a placeholder until the pen
// line's compounding/testing facts are confirmed.
//
// The pens are hard-coded, promotable products (lib/compliance.ts): a
// GLP-class code-name product must never appear here. Cut-out renders
// (transparent background) — see public/products/hero/README.md.
const HERO_PENS = { front: "/products/hero/bpc-157.png", back: "/products/hero/tb-500.png" };

const BADGES = [
  { icon: "pen", label: "3 mL auto-injector pens" },
  { icon: "check", label: "Ready to use" },
  { icon: "flag", label: "Research use only" },
] as const;

export default function HomeHero() {
  return (
    <section className={styles.hero}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <h1 className={styles.headline}>
            Research peptides
            <br />
            in pre-filled auto-injector pens,
            <br />
            <strong>ready to use — no reconstitution</strong>
          </h1>
          <Link href="/shop" className={`button buttonPill ${styles.cta}`}>
            Shop Pens
          </Link>
        </div>

        <div className={styles.visual} aria-hidden="true">
          <div className={styles.stage}>
            <span className={styles.shadow} />
            {/* eslint-disable-next-line @next/next/no-img-element -- product renders are static files under public/products */}
            <img src={HERO_PENS.back} alt="" width={830} height={195} className={`${styles.pen} ${styles.penBack}`} />
            {/* eslint-disable-next-line @next/next/no-img-element -- see above */}
            <img src={HERO_PENS.front} alt="" width={830} height={195} className={`${styles.pen} ${styles.penFront}`} />
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
