import Link from "next/link";
import { BAC_WATER_SLUG, isSupply } from "@/lib/supplies";
import styles from "./FormatNotice.module.css";

// Generic, legally-safe copy: not dosing or reconstitution instructions,
// which would need real content from David. Keyed off the variant's raw
// `form` (not the display label), since that's the stable value this
// should branch on. BAC water is a diluent, not a lyophilized compound,
// so it gets its own line.
const NOTICES: Record<string, string> = {
  pen: "Ships as a pre-filled 3 mL auto-injector pen. No reconstitution required.",
  lyophilized:
    "Ships as a lyophilized (freeze-dried) powder in a sealed vial. Reconstitution with an appropriate diluent is required before use.",
  preconstituted: "Ships pre-mixed and ready to use. No reconstitution required.",
};

export default function FormatNotice({ form, productSlug }: { form: string | null; productSlug?: string }) {
  if (productSlug && isSupply(productSlug)) {
    return (
      <p className={styles.notice}>
        Sterile bacteriostatic water, the standard diluent for reconstituting lyophilized vials. A supply, not a
        research compound.
      </p>
    );
  }
  if (!form) return null;
  const notice = NOTICES[form];
  if (!notice) return null;

  return (
    <p className={styles.notice}>
      {notice}
      {form === "lyophilized" && (
        <>
          {" "}
          Bacteriostatic water is <Link href={`/shop/${BAC_WATER_SLUG}`}>listed in the catalog</Link>.
        </>
      )}
    </p>
  );
}
