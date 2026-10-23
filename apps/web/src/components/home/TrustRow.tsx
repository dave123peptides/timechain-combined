import SectionIcon from "@/components/SectionIcon";
import styles from "./TrustRow.module.css";

// Four facts in one quiet line under the hero. Each is one this codebase
// or David stands behind (SELLABLE_FORMS, the FAQ sourcing claim, the
// certificate policy); nothing about purity, speed or shipping.
const FACTS = [
  { icon: "flag", text: "Compounded, tested and verified in the United States" },
  { icon: "vial", text: "Pre-filled pens and lyophilized vials" },
  { icon: "document", text: "Certificates of Analysis on request" },
  { icon: "shield", text: "For laboratory research use only" },
] as const;

export default function TrustRow() {
  return (
    <section className={styles.row} aria-label="About our products">
      <ul className={`container ${styles.list}`}>
        {FACTS.map((fact) => (
          <li key={fact.text} className={styles.item}>
            <SectionIcon name={fact.icon} size={16} />
            <span>{fact.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
