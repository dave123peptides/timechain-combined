import type { ReactNode } from "react";
import styles from "./PageBanner.module.css";

// Page-top banner (Core reference, 9/4), two variants:
//  - "dark": the shop banner — dark on the left under the copy, fading
//    to white on the right so the pen renders (white bodies, red labels)
//    sit on white and stay legible. (A white wedge cutting through the
//    renders and a glow on plain dark were both tried first — David, 9/5.)
//  - "light": the about banner — white left with a big uppercase accent
//    title, a dark diagonal panel on the right.
// The reference uses lab photography; we have none, so both variants are
// gradients. (The honeycomb lattice was parked at David's request.)
// `images` are cut-out pen renders (public/products/hero, landscape
// 830x195) of hard-coded promotable products (lib/compliance.ts) — never
// a GLP-class code-name product.
export default function PageBanner({
  variant,
  eyebrow,
  title,
  images,
  children,
}: {
  variant: "dark" | "light";
  eyebrow?: string;
  title: string;
  images?: string[];
  children?: ReactNode;
}) {
  const dark = variant === "dark";
  return (
    <section className={`${styles.banner} ${dark ? styles.dark : styles.light}`}>
      {!dark && <div className={styles.panel} aria-hidden="true" />}
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          {eyebrow && <span className={`eyebrow ${styles.eyebrow}`}>{eyebrow}</span>}
          <h1 className={styles.title}>{title}</h1>
          {children}
        </div>
        {images && images.length > 0 && (
          <div className={styles.pens} aria-hidden="true">
            {images.map((src, index) => (
              // eslint-disable-next-line @next/next/no-img-element -- product renders are static files under public/products
              <img key={src} src={src} alt="" width={830} height={195} className={`${styles.pen} ${styles[`pen${index}`]}`} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
