"use client";

import styles from "./QuantityStepper.module.css";

// Shared by the PDP variant picker, the sticky buy bar and the cart rows,
// which each previously rendered a bare <input type="number">. Those are
// close to unusable on a phone: the spinner arrows are a few pixels tall
// and only appear on hover. The -/+ buttons here are 2.75rem (44px) so
// they clear the minimum touch-target size.
export default function QuantityStepper({
  value,
  onChange,
  min = 1,
  max,
  disabled = false,
  label = "Quantity",
  compact = false,
}: {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
  label?: string;
  compact?: boolean;
}) {
  const clamp = (n: number) => {
    if (Number.isNaN(n)) return min;
    if (n < min) return min;
    if (max !== undefined && n > max) return max;
    return n;
  };

  return (
    <div className={`${styles.stepper} ${compact ? styles.compact : ""}`}>
      <button
        type="button"
        className={styles.button}
        onClick={() => onChange(clamp(value - 1))}
        disabled={disabled || value <= min}
        aria-label={`Decrease ${label.toLowerCase()}`}
      >
        −
      </button>
      <input
        type="number"
        className={styles.input}
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        aria-label={label}
        // Not clamped on every keystroke: clearing the field to type "12"
        // would otherwise snap it straight back to the minimum. An empty
        // or partial value settles to a valid one on blur.
        onChange={(event) => {
          const raw = event.target.value;
          if (raw === "") return;
          onChange(clamp(Number(raw)));
        }}
        onBlur={(event) => onChange(clamp(Number(event.target.value)))}
      />
      <button
        type="button"
        className={styles.button}
        onClick={() => onChange(clamp(value + 1))}
        disabled={disabled || (max !== undefined && value >= max)}
        aria-label={`Increase ${label.toLowerCase()}`}
      >
        +
      </button>
    </div>
  );
}
