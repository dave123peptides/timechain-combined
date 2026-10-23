import Link from "next/link";
import { ORDERING_ENABLED } from "@/lib/site";
import styles from "./Footer.module.css";

// Core-reference footer (9/4): brand + tagline, Quick links, Legal. No
// payment column (David, 9/5), and on this site no payments at all. No
// entity line: the LLC name stays off the storefront (David,
// 2026-09-06).
//
// No Shipping or Returns link: /shipping is deliberately not built. The
// carrier, cutoff and processing times are unconfirmed, and a
// linked-but-vague shipping page is a published shipping claim by another
// name. Add both once David supplies the facts.
export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className="container">
        <div className={styles.grid}>
          <div>
            <div className={styles.wordmark}>
              Time<span>Chain</span>
            </div>
            <p className={styles.tagline}>
              Research peptides in pre-filled auto-injector pens and lyophilized vials, for laboratory and
              research use.
            </p>
          </div>
          <div>
            <div className={styles.heading}>Quick links</div>
            <div className={styles.linkList}>
              <Link href="/shop">Shop</Link>
              <Link href="/shop?form=pen">Pens</Link>
              <Link href="/shop?form=lyophilized">Vials</Link>
              <Link href="/coa">Certificates of Analysis</Link>
              <Link href="/faq">FAQ</Link>
              <Link href="/contact">Contact</Link>
              {ORDERING_ENABLED && <Link href="/cart">Cart</Link>}
            </div>
          </div>
          <div>
            <div className={styles.heading}>Legal</div>
            <div className={styles.linkList}>
              <Link href="/research-use-only">Research Use Only</Link>
              <Link href="/terms">Terms</Link>
              <Link href="/privacy">Privacy</Link>
            </div>
          </div>
        </div>
        <p className={styles.disclaimer}>
          All products offered by TimeChain are intended strictly for laboratory and research use only. They are
          not drugs, dietary supplements, cosmetics, or food; are not intended for human or veterinary use; and are
          not intended to diagnose, treat, cure, or prevent any disease. Not for human consumption.
        </p>
      </div>
    </footer>
  );
}
