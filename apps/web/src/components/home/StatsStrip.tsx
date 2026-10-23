import styles from "./StatsStrip.module.css";

// The navy stats band under the hero (BioLongevity and American Peptides
// pattern). Every number is read from the live catalog on each render,
// never typed in; the two text tiles are facts this codebase or David
// stands behind.
export default function StatsStrip({ compounds, configurations, formats }: { compounds: number; configurations: number; formats: number }) {
  const items = [
    { value: String(compounds), label: "Compounds in the catalog" },
    { value: String(configurations), label: "Format and strength configurations" },
    { value: String(formats), label: formats === 1 ? "Format" : "Formats: pens and vials" },
    { value: "USA", label: "Compounded, tested and verified" },
  ];
  return (
    <section className={styles.band} aria-label="Catalog at a glance">
      <div className={`container ${styles.grid}`}>
        {items.map((item) => (
          <div key={item.label} className={styles.item}>
            <span className={styles.value}>{item.value}</span>
            <span className={styles.label}>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
