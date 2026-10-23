import type { ReactNode } from "react";
import styles from "./PageBanner.module.css";

// Page-top band (B2B redesign, 2026-10-22): paper ground, serif title
// with an optional italic accent, a lede, and the pen renders fanned on
// the right when a page passes them. `images` are cut-out renders of
// promotable products only (lib/compliance.ts), never a GLP-class
// code-name product. `variant` is kept for callers; both render the same
// band now.
export default function PageBanner({
  eyebrow,
  title,
  images,
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
        <div className={styles.copy}>
          {eyebrow && <span className={`eyebrow ${styles.eyebrow}`}>{eyebrow}</span>}
          <h1 className={styles.title}>{title}</h1>
          {children}
        </div>
        {images && images.length > 0 && (
          <div className={styles.pens} aria-hidden="true">
            {images.slice(0, 3).map((src, index) => (
              // eslint-disable-next-line @next/next/no-img-element -- static renders under public/products/hero
              <img key={src} src={src} alt="" width={830} height={195} className={`${styles.pen} ${styles[`pen${index}`]}`} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
