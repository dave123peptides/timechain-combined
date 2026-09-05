import styles from "./FormatNotice.module.css";

// Generic, legally-safe copy — not dosing/reconstitution instructions,
// which would need real content from David. Keyed off the variant's raw
// `form` (not the display label), since that's the stable value this
// should branch on.
const NOTICES: Record<string, string> = {
  pen: "Ships as a pre-filled 3 mL auto-injector pen. No reconstitution required.",
  lyophilized:
    "Ships as a lyophilized (freeze-dried) powder. Reconstitution with an appropriate diluent is required before use.",
  preconstituted: "Ships pre-mixed and ready to use — no reconstitution required.",
};

export default function FormatNotice({ form }: { form: string | null }) {
  if (!form) return null;
  const notice = NOTICES[form];
  if (!notice) return null;

  return <p className={styles.notice}>{notice}</p>;
}
