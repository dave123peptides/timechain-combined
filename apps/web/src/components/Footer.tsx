import Link from "next/link";
import { ORDERING_ENABLED, SUPPORT_EMAIL } from "@/lib/site";
import styles from "./Footer.module.css";

// Minimal footer: a thin rule, three link columns, the support address,
// and the research-use-only line. No entity line (David, 2026-09-06).
export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className="container">
        <div className={styles.grid}>
          <div className={styles.brand}>
            <div className={styles.wordmark}>
              <span className={styles.mark} aria-hidden="true" />
              TimeChain <span>Peptides</span>
            </div>
            <p className={styles.tagline}>
              Research peptides in pre-filled pens and lyophilized vials, supplied in quantity to research
              organizations and medical practices.
            </p>
            <a href={`mailto:${SUPPORT_EMAIL}`} className={styles.email}>
              {SUPPORT_EMAIL}
            </a>
          </div>
          <div>
            <div className={styles.heading}>Catalog</div>
            <div className={styles.linkList}>
              <Link href="/shop">All compounds</Link>
              <Link href="/shop?form=pen">Pens</Link>
              <Link href="/shop?form=lyophilized">Vials</Link>
              <Link href="/coa">Certificates of Analysis</Link>
              {ORDERING_ENABLED && <Link href="/cart">Cart</Link>}
            </div>
          </div>
          <div>
            <div className={styles.heading}>Ordering</div>
            <div className={styles.linkList}>
              <Link href="/book">Book a meeting</Link>
              <Link href="/request">Your order request</Link>
              <Link href="/#how-it-works">How ordering works</Link>
              <Link href="/contact">Contact</Link>
              <Link href="/faq">FAQ</Link>
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
