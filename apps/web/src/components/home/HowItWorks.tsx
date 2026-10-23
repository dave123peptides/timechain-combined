import Link from "next/link";
import styles from "./HowItWorks.module.css";

// Three steps (Ascend's "how a vial reaches you", redirected at ordering):
// what happens from the catalog to an arranged order. No turnaround
// promise: none has been confirmed.
const STEPS = [
  {
    title: "Build your request",
    body: "Add compounds from the catalog. Pick pen or vial, the strength, and the quantity. Edit the list any time before you send it.",
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
      <div className="container">
        <div className={styles.head}>
          <span className="eyebrow">How ordering works</span>
          <h2>
            Three steps, <em>no checkout.</em>
          </h2>
        </div>
        <ol className={styles.steps}>
          {STEPS.map((step, index) => (
            <li key={step.title} className={styles.step}>
              <span className={styles.number}>0{index + 1}</span>
              <h3 className={styles.title}>{step.title}</h3>
              <p className={styles.body}>{step.body}</p>
            </li>
          ))}
        </ol>
        <div className={styles.actions}>
          <Link href="/shop" className="button buttonAccent">
            Start a request
          </Link>
          <Link href="/contact" className="button buttonAccentOutline">
            Talk with us first
          </Link>
        </div>
      </div>
    </section>
  );
}
