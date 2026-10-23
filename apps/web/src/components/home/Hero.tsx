import Link from "next/link";
import SectionIcon from "@/components/SectionIcon";
import { AUDIENCE } from "@/lib/site";
import styles from "./Hero.module.css";

// Hero (B2B redesign, 2026-10-22, after the OT and Ascend references): a
// serif headline with one italic accent line, the proposition in a
// sentence, two actions, and the products on a pedestal card with three
// callouts. Real claims only: two formats (SELLABLE_FORMS on the API),
// pens ready to use, vials lyophilized, the US compounding and testing
// claim David made for the FAQ. Nothing about purity, speed or shipping.
//
// The pen is a hard-coded promotable product (lib/compliance.ts); the
// vial photo is the same compound's vial. Never a GLP-class code name.
const PEN = "/products/hero/bpc-157.png";
const VIAL = "/products/bpc-157-2.png";

const CALLOUTS = [
  { icon: "pen", label: "3 mL auto-injector pens" },
  { icon: "vial", label: "Lyophilized vials" },
  { icon: "flag", label: "Research use only" },
] as const;

export default function Hero() {
  return (
    <section className={styles.hero}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <span className="eyebrow">Research peptides, supplied in quantity</span>
          <h1 className={styles.headline}>
            Research peptides for <em>{AUDIENCE}.</em>
          </h1>
          <p className={styles.lede}>
            Pre-filled auto-injector pens and lyophilized vials, compounded, tested and verified in the United
            States. Build an order request in the quantities your work needs, and we take it from there.
          </p>
          <div className={styles.actions}>
            <Link href="/shop" className="button buttonAccent">
              Browse the catalog
            </Link>
            <Link href="#how-it-works" className="button buttonAccentOutline">
              How ordering works
            </Link>
          </div>
        </div>

        <div className={styles.visual} aria-hidden="true">
          <div className={styles.pedestal}>
            <span className={styles.code}>TC · 01</span>
            {/* eslint-disable-next-line @next/next/no-img-element -- static renders under public/products */}
            <img src={VIAL} alt="" className={`${styles.vial} productPhoto`} />
            {/* eslint-disable-next-line @next/next/no-img-element -- see above */}
            <img src={PEN} alt="" width={830} height={195} className={styles.pen} />
          </div>
          <ul className={styles.callouts}>
            {CALLOUTS.map((callout) => (
              <li key={callout.label} className={styles.callout}>
                <SectionIcon name={callout.icon} size={13} />
                {callout.label}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
