import type { ProductContent } from "@/lib/api";
import styles from "./sections.module.css";

export default function ResearchAreas({ content }: { content: ProductContent }) {
  if (content.research_areas.length === 0) return null;

  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <span className="eyebrow">Research Applications</span>
        <h2>Where This Shows Up in Research</h2>
      </div>
      <div className={styles.researchGrid}>
        {content.research_areas.map((area) => (
          <div key={area} className={styles.researchCard}>
            {area}
          </div>
        ))}
      </div>
    </section>
  );
}
