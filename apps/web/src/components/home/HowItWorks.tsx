import Link from "next/link";
import { BOOKING_HREF, BOOKING_TARGET } from "@/lib/site";
import styles from "./HowItWorks.module.css";

// Three steps from the catalog to an arranged order (David, 2026-10-23:
// the meeting is the only action on the site). No turnaround promise:
// none has been confirmed.
const STEPS = [
  {
    title: "Review the catalog",
    body: "Browse by category. Every compound shows the formats it ships in and the strengths offered, with certificates where we hold them.",
  },
  {
    title: "Book a meeting",
    body: "A short call with the people who run the catalog: which formats and strengths fit your practice, quantities, documentation and pricing.",
  },
  {
    title: "The order is arranged directly",
    body: "Fulfillment, documentation and terms are agreed with you after the call. No payment is taken on this site.",
  },
];

export default function HowItWorks() {
  return (
    <section className={styles.section} id="how-it-works">
      <div className={`container ${styles.inner}`}>
        <div className={styles.head}>
          <span className="eyebrow">How it works</span>
          <h2>
            Three steps. <em>No checkout.</em>
          </h2>
          <div className={styles.actions}>
            <a href={BOOKING_HREF} {...BOOKING_TARGET} className="button buttonAccent">
              Book a meeting
            </a>
            <Link href="/shop" className="button buttonAccentOutline">
              Open the catalog
            </Link>
          </div>
        </div>
        <ol className={styles.steps}>
          {STEPS.map((step, index) => (
            <li key={step.title} className={styles.step}>
              <span className={styles.number}>{index + 1}</span>
              <div>
                <h3 className={styles.title}>{step.title}</h3>
                <p className={styles.body}>{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
