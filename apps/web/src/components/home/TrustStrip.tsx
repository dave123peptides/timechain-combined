import Link from "next/link";
import SectionIcon from "@/components/SectionIcon";
import styles from "./TrustStrip.module.css";

// The black pill band under the hero (Core reference, 9/4). Three items,
// each a fact this codebase or David can stand behind, see HomeHero's
// note. Core's middle item is "Free delivery over $200"; no threshold
// exists here, so the slot carries the two-format fact instead.
//
// TODO(David): the catalog holds no third-party certificates yet, so the
// first item says "on request" rather than "published per lot". Restore
// the published-per-lot wording only once COAs are loaded.
const ITEMS = [
  {
    icon: "shield",
    title: "Certificates on request",
    body: (
      <>
        A Certificate of Analysis for any batch is available on request from support@timechainpeptides.com.
        Published certificates open the laboratory&apos;s own copy.
      </>
    ),
  },
  {
    icon: "vial",
    title: "Pens and vials",
    body: (
      <>
        Every compound is listed in the format it ships in: a pre-filled 3 mL auto-injector pen, a lyophilized
        vial for reconstitution, or both. Enforced in our catalog, not just stated.
      </>
    ),
  },
  {
    icon: "chat",
    title: "Talk with us",
    body: (
      <>
        Book a meeting from the <Link href="/contact">Contact page</Link> or email support@timechainpeptides.com.
        It reaches a person, not a ticket queue.
      </>
    ),
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
