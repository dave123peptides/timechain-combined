import type { CoaCardGroup } from "@/lib/coa";
import CoaCard from "./CoaCard";
import styles from "./coa.module.css";

// The certificate card grid, shared by the PDP's Lab report tab and /coa,
// which differ only in what the cards are titled. Plain markup: each
// card's links open the lab's PDF in a new tab, so there is no viewer
// state to hold.
export default function CoaGrid({ groups }: { groups: CoaCardGroup[] }) {
  return (
    <div className={styles.grid}>
      {groups.map((group) => (
        <CoaCard key={group.key} group={group} />
      ))}
    </div>
  );
}
