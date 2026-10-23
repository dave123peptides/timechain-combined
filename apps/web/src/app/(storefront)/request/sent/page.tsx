import Link from "next/link";
import { BOOK_PATH } from "@/lib/site";
import styles from "./page.module.css";

export const metadata = { title: "Request received" };

// Landing after a sent order request. The reference is the one thing the
// requester keeps; it is also what the CRM received.
export default async function RequestSentPage({ searchParams }: { searchParams: Promise<{ ref?: string }> }) {
  const { ref } = await searchParams;
  const reference = ref && /^REQ-[A-Z0-9]{6,8}$/.test(ref) ? ref : null;

  return (
    <main className={`container ${styles.page}`}>
      <span className="eyebrow">Order request</span>
      <h1>
        Received. <em>We&apos;ll be in touch.</em>
      </h1>
      {reference && (
        <p className={styles.reference}>
          Your reference is <strong>{reference}</strong>. Keep it for any follow-up.
        </p>
      )}
      <ol className={styles.steps}>
        <li>
          <strong>We review your list.</strong> Availability for each format and strength at the quantities you asked
          for, and the documentation you need.
        </li>
        <li>
          <strong>You hear back by email.</strong> Pricing for your quantities, lead times and any questions, from the
          people who run the catalog.
        </li>
        <li>
          <strong>The order is arranged directly.</strong> No payment is taken on this site.
        </li>
      </ol>
      <div className={styles.actions}>
        <Link href={BOOK_PATH} className="button buttonAccent">
          Book a meeting to go through it
        </Link>
        <Link href="/shop" className="button buttonAccentOutline">
          Back to the catalog
        </Link>
      </div>
    </main>
  );
}
