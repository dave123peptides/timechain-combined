import Link from "next/link";
import { BOOK_PATH } from "@/lib/site";
import styles from "./HowItWorks.module.css";

// Three steps from the catalog to an arranged order. No turnaround
// promise: none has been confirmed.
const STEPS = [
  {
    title: "Review the catalog, or book a call",
    body: "Browse by category and add compounds, formats, strengths and quantities to a request. Or book a meeting and we go through it with you.",
  },
  {
    title: "We review and reply",
    body: "You hear back by email with availability, documentation and pricing for your quantities, from the people who run the catalog.",
  },
  {
    title: "The order is arranged directly",
    body: "Fulfillment, documentation and terms are agreed with you. No payment is taken on this site.",
  },
];

export default function HowItWorks() {
  return (
    <section className={styles.section} id="how-it-works">
      <div className={`container ${styles.inner}`}>
        <div className={styles.head}>
          <span className="eyebrow">How ordering works</span>
          <h2>
            Three steps. <em>No checkout.</em>
          </h2>
          <div className={styles.actions}>
            <Link href={BOOK_PATH} className="button buttonAccent">
              Book a meeting
            </Link>
            <Link href="/shop" className="button buttonAccentOutline">
              Start a request
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
