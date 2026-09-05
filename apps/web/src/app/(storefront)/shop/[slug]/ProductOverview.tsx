import type { ProductContent } from "@/lib/api";
import styles from "./sections.module.css";

export default function ProductOverview({ name, content }: { name: string; content: ProductContent }) {
  if (!content.overview && content.key_points.length === 0) return null;

  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <span className="eyebrow">Research Overview</span>
        <h2>What Is {name}?</h2>
      </div>
      <div className={styles.sectionGrid}>
        {content.overview && <p className={styles.overview}>{content.overview}</p>}
        {content.key_points.length > 0 && (
          <ul className={styles.keyPoints}>
            {content.key_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
