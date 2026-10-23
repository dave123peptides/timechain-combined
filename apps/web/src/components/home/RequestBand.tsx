import Link from "next/link";
import { BOOKING_URL, CONTACT_PATH } from "@/lib/site";
import styles from "./RequestBand.module.css";

// The closing call to action on navy: the request, or a conversation.
export default function RequestBand() {
  return (
    <section className={styles.band}>
      <div className={`container ${styles.inner}`}>
        <div>
          <span className={`eyebrow ${styles.eyebrow}`}>Ready when you are</span>
          <h2 className={styles.title}>
            Build your order request, <em>or talk with us first.</em>
          </h2>
        </div>
        <div className={styles.actions}>
          <Link href="/shop" className="button buttonOnDark">
            Browse the catalog
          </Link>
          {BOOKING_URL ? (
            <a href={BOOKING_URL} target="_blank" rel="noopener noreferrer" className={`button ${styles.outline}`}>
              Book a meeting
            </a>
          ) : (
            <Link href={CONTACT_PATH} className={`button ${styles.outline}`}>
              Contact us
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
