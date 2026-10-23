import Link from "next/link";
import styles from "./FormatsSection.module.css";

// The two formats, side by side, each a fact enforced in code
// (SELLABLE_FORMS) with the handling note FormatNotice gives on every
// product page. Photos: a promotable product's pen render and its vial.
const FORMATS = [
  {
    key: "pen",
    eyebrow: "Format 01",
    title: "Pre-filled pens",
    body: "A 3 mL auto-injector pen, filled and ready to use in a research setting. No reconstitution, no diluent.",
    image: "/products/hero/tb-500.png",
    pen: true,
    href: "/shop?form=pen",
    cta: "Browse pens",
  },
  {
    key: "lyophilized",
    eyebrow: "Format 02",
    title: "Lyophilized vials",
    body: "Freeze-dried powder in a sealed vial, reconstituted with an appropriate diluent before use. Bacteriostatic water is listed in the catalog.",
    image: "/products/tb-500-lyo.png",
    pen: false,
    href: "/shop?form=lyophilized",
    cta: "Browse vials",
  },
];

export default function FormatsSection() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.head}>
          <span className="eyebrow">Two formats</span>
          <h2>
            The same compounds, <em>your choice of format.</em>
          </h2>
          <p className={styles.lede}>
            Most compounds ship as either. Each product page lists what is offered and lets you add any mix of
            formats and strengths to one request.
          </p>
        </div>
        <div className={styles.grid}>
          {FORMATS.map((format) => (
            <article key={format.key} className={styles.card}>
              <div className={styles.media} aria-hidden="true">
                {/* eslint-disable-next-line @next/next/no-img-element -- static product files */}
                <img src={format.image} alt="" className={`${format.pen ? styles.penImage : styles.vialImage} productPhoto`} />
              </div>
              <div className={styles.body}>
                <span className={styles.cardEyebrow}>{format.eyebrow}</span>
                <h3 className={styles.title}>{format.title}</h3>
                <p className={styles.text}>{format.body}</p>
                <Link href={format.href} className={styles.link}>
                  {format.cta}
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
