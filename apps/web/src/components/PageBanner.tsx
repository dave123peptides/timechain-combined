import type { ReactNode } from "react";
import styles from "./PageBanner.module.css";

// Page-top band (modern, minimal, 2026-10-22): eyebrow, headline, lede.
// `images` and `variant` are accepted for older callers and ignored:
// there is no product art up here any more.
export default function PageBanner({
  eyebrow,
  title,
  children,
}: {
  variant?: "dark" | "light";
  eyebrow?: string;
  title: ReactNode;
  images?: string[];
  children?: ReactNode;
}) {
  return (
    <section className={styles.banner}>
      <div className={`container ${styles.inner}`}>
        {eyebrow && <span className={`eyebrow ${styles.eyebrow}`}>{eyebrow}</span>}
        <h1 className={styles.title}>{title}</h1>
        {children}
      </div>
    </section>
  );
}
