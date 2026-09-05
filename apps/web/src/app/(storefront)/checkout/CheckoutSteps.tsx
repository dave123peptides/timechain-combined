import SectionIcon from "@/components/SectionIcon";
import styles from "./page.module.css";

export const STEPS = ["Information", "Shipping", "Payment"] as const;
export type StepIndex = 0 | 1 | 2;

// The numbered progress line beside the "Checkout" title (Core
// reference, 9/4): completed steps show a check, the current one its
// number in the accent, later ones outlined.
export default function CheckoutSteps({ current }: { current: StepIndex }) {
  return (
    <ol className={styles.steps} aria-label="Checkout progress">
      {STEPS.map((label, index) => {
        const state = index < current ? "done" : index === current ? "current" : "todo";
        return (
          <li key={label} className={`${styles.step} ${styles[`step_${state}`]}`} aria-current={state === "current" ? "step" : undefined}>
            <span className={styles.stepCircle}>
              {state === "done" ? <SectionIcon name="check" size={18} /> : index + 1}
            </span>
            <span className={styles.stepLabel}>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
