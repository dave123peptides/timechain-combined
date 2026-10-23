import Link from "next/link";
import { BOOK_PATH } from "@/lib/site";
import styles from "./BookSection.module.css";

// The homepage's case for the meeting (David, 2026-10-23: the primary
// action is booking a call to go through the catalog). Plain statements
// of what the call covers; no duration or turnaround promise.
const POINTS = [
  "Which compounds, formats and strengths fit your practice or lab",
  "Quantities, availability and lead times at the volumes you need",
  "Certificates of Analysis and the documentation your compliance needs",
  "Pricing for your quantities and how ordering is arranged",
];

export default function BookSection() {
  return (
    <section className={styles.section} id="book">
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <span className="eyebrow">Talk it through</span>
          <h2>
            Review the catalog, <em>then book a call with us.</em>
          </h2>
          <p className={styles.lede}>
            The fastest way to get answers for your practice is a short conversation with the people who run the
            catalog. Come with your list, or let us build it with you.
          </p>
          <div className={styles.actions}>
            <Link href={BOOK_PATH} className="button buttonAccent">
              Book a meeting
            </Link>
            <Link href="/shop" className="button buttonAccentOutline">
              Build an order request instead
            </Link>
          </div>
        </div>
        <ul className={styles.points}>
          {POINTS.map((point, index) => (
            <li key={point} className={styles.point}>
              <span className={styles.pointNumber}>{index + 1}</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
