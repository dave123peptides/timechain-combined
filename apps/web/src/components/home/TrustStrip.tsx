import SectionIcon from "@/components/SectionIcon";
import styles from "./TrustStrip.module.css";

// The black pill band under the hero (Core reference, 9/4). Three items,
// each a fact this codebase or David can stand behind — see HomeHero's
// note. Core's middle item is "Free delivery over $200"; no threshold
// exists here (system_settings holds only a flat rate), so the slot
// carries the lyophilized-only guarantee instead.
const ITEMS = [
  {
    icon: "shield",
    title: "Third-party tested",
    body: "Certificates of Analysis are published per lot and open the laboratory's own copy. Verify the code with the lab directly.",
  },
  {
    icon: "vial",
    title: "Lyophilized only",
    body: "Every product ships as a freeze-dried vial. No pens, no pre-constituted formats. Enforced in our catalog, not just stated.",
  },
  {
    icon: "chat",
    title: "Direct support",
    body: "Have a question? Email support@timechainpeptides.com. It reaches a person, not a ticket queue.",
  },
] as const;

export default function TrustStrip() {
  return (
    <div className="container">
      <div className={styles.strip}>
        {ITEMS.map((item) => (
          <div key={item.title} className={styles.item}>
            <span className={styles.icon}>
              <SectionIcon name={item.icon} size={30} />
            </span>
            <div>
              <div className={styles.title}>{item.title}</div>
              <p className={styles.body}>{item.body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
