import Link from "next/link";
import SectionIcon from "@/components/SectionIcon";
import { BOOKING_EMBED, BOOKING_URL, SUPPORT_EMAIL } from "@/lib/site";
import styles from "./page.module.css";

export const metadata = { title: "Book a meeting" };

// The booking page (David, 2026-10-23): the site's primary action. The
// calendar David supplies (NEXT_PUBLIC_BOOKING_URL) is embedded here so a
// practice books without leaving the site, with the same link offered in
// a new tab for anyone whose browser blocks the frame. Until the link
// exists the page offers email, so it never dead-ends. What the call
// covers is stated plainly; no duration or response-time promise, since
// none has been confirmed.
const COVERS = [
  { icon: "layers", title: "The catalog, for your practice", body: "Which compounds, formats and strengths fit what you do, and what each ships as." },
  { icon: "record", title: "Quantities and lead times", body: "What you need per month or per order, and how availability works at those quantities." },
  { icon: "document", title: "Documentation", body: "Certificates of Analysis, safety data sheets and anything else your compliance needs." },
  { icon: "chat", title: "Pricing and terms", body: "Pricing for your quantities, how ordering is arranged, and how to reach us afterwards." },
] as const;

export default function BookPage() {
  return (
    <main className={`container ${styles.page}`}>
      <header className={styles.head}>
        <span className="eyebrow">Book a meeting</span>
        <h1>
          Walk through the catalog <em>with us.</em>
        </h1>
        <p className={styles.lede}>
          A short call about what your practice or lab needs. Bring your questions, or build an order request first
          and we go through it together. No payment is taken on this site; everything is arranged after we talk.
        </p>
      </header>

      <div className={styles.layout}>
        <aside className={styles.aside}>
          <h2 className={styles.asideTitle}>What we cover</h2>
          <ul className={styles.covers}>
            {COVERS.map((item) => (
              <li key={item.title} className={styles.cover}>
                <span className={styles.coverIcon}>
                  <SectionIcon name={item.icon} size={18} />
                </span>
                <div>
                  <span className={styles.coverTitle}>{item.title}</span>
                  <p className={styles.coverBody}>{item.body}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className={styles.asideNote}>
            Rather not book? Email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> or{" "}
            <Link href="/shop">send an order request</Link> from the catalog.
          </p>
        </aside>

        <section className={styles.calendar} aria-label="Pick a time">
          {BOOKING_URL ? (
            <>
              {BOOKING_EMBED ? (
                <iframe src={BOOKING_URL} title="Book a meeting" className={styles.frame} loading="lazy" allow="payment *" />
              ) : (
                <div className={styles.fallback}>
                  <p>Pick a time on our calendar.</p>
                </div>
              )}
              <div className={styles.calendarActions}>
                <a href={BOOKING_URL} target="_blank" rel="noopener noreferrer" className="button buttonAccent">
                  Open the calendar in a new tab
                </a>
              </div>
            </>
          ) : (
            <div className={styles.fallback}>
              <h2 className={styles.fallbackTitle}>Email us to book a time.</h2>
              <p>
                Tell us roughly when suits you and what you would like to cover. We reply from{" "}
                {SUPPORT_EMAIL} with times.
              </p>
              <a href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("Meeting request")}`} className="button buttonAccent">
                Email us to book a meeting
              </a>
            </div>
          )}
          <p className={styles.ruo}>Everything we supply is for laboratory research use only.</p>
        </section>
      </div>
    </main>
  );
}
