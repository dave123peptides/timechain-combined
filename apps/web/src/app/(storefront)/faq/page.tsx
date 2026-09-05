import Faq from "@/components/Faq";
import { SITE_FAQ } from "@/lib/faqContent";
import styles from "../legal.module.css";

export const metadata = { title: "FAQ | TCP" };

export default function FaqPage() {
  return (
    <main className={styles.wrap}>
      <span className={`eyebrow ${styles.eyebrow}`}>Questions</span>
      <h1>Frequently Asked Questions</h1>

      <p>
        Shared with the homepage from a single list, so the two can never disagree. If something isn&apos;t
        answered here, email <a href="mailto:support@timechainpeptides.com">support@timechainpeptides.com</a> — we&apos;d rather tell you we don&apos;t know
        yet than guess.
      </p>

      <Faq entries={SITE_FAQ} />
    </main>
  );
}
