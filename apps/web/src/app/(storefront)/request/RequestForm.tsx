"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ApiError, createOrderRequest, formatStrength } from "@/lib/api";
import { formSingular } from "@/lib/forms";
import { useOrderRequest } from "@/lib/request-context";
import { BOOKING_URL, CONTACT_PATH, SUPPORT_EMAIL } from "@/lib/site";
import { useResolvedRequest } from "@/lib/useResolvedRequest";
import ProductImagePlaceholder from "@/components/ProductImagePlaceholder";
import QuantityStepper from "@/components/QuantityStepper";
import SectionIcon from "@/components/SectionIcon";
import styles from "./page.module.css";

const ROLES = ["Physician or provider", "Practice manager", "Researcher", "Procurement", "Other"];

// Two columns: the request list (editable, same lines as the drawer) and
// the contact form. Nothing here is money. On success the list is cleared
// and the reference shown on /request/sent.
export default function RequestForm() {
  const router = useRouter();
  const pathname = usePathname();
  const { setQuantity, removeItem, clear } = useOrderRequest();
  const { hydrated, loading, loadError, lines, hasUnavailable, canSubmit } = useResolvedRequest();
  const id = useId();

  const [name, setName] = useState("");
  const [organization, setOrganization] = useState("");
  const [role, setRole] = useState(ROLES[0]);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [region, setRegion] = useState("");
  const [notes, setNotes] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const available = lines.filter((line) => line.variant);
  const units = available.reduce((sum, line) => sum + line.quantity, 0);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await createOrderRequest({
        name,
        organization,
        email,
        role,
        phone: phone || null,
        region: region || null,
        notes: notes || null,
        items: available.map((line) => ({ variant_id: line.variantId, quantity: line.quantity })),
        source_path: pathname,
        website,
      });
      clear();
      router.push(`/request/sent?ref=${encodeURIComponent(result.reference)}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : `We couldn't send the request. Try again, or email ${SUPPORT_EMAIL} with your list.`
      );
      setSubmitting(false);
    }
  };

  return (
    <main className={`container ${styles.page}`}>
      <header className={styles.head}>
        <span className="eyebrow">Order request</span>
        <h1>
          Tell us what you need, <em>in the quantities you need.</em>
        </h1>
        <p className={styles.lede}>
          Review your list, add your details, and send. We reply by email with availability, documentation and
          pricing for these quantities, then arrange the order with you. No payment is taken on this site.
        </p>
      </header>

      <div className={styles.layout}>
        <section className={styles.list} aria-labelledby={`${id}-list`}>
          <div className={styles.listHead}>
            <h2 id={`${id}-list`} className={styles.listTitle}>
              Your list
            </h2>
            <span className={styles.listCount}>
              {hydrated && lines.length > 0 ? `${lines.length} ${lines.length === 1 ? "line" : "lines"} · ${units} units` : ""}
            </span>
          </div>

          {!hydrated || (loading && lines.length > 0) ? (
            <p className={styles.muted}>Checking availability…</p>
          ) : lines.length === 0 ? (
            <div className={styles.empty}>
              <p>Your list is empty. Add compounds from the catalog with the format, strength and quantity you need.</p>
              <Link href="/shop" className="button buttonAccentOutline">
                Browse the catalog
              </Link>
            </div>
          ) : (
            <ul className={styles.lines}>
              {lines.map((line) => (
                <li key={line.variantId} className={styles.line}>
                  <div className={styles.thumb}>
                    {line.image ? (
                      // eslint-disable-next-line @next/next/no-img-element -- static product files
                      <img src={line.image} alt="" className={`${styles.thumbImage} productPhoto`} />
                    ) : (
                      <ProductImagePlaceholder name={line.productName ?? "?"} />
                    )}
                  </div>
                  <div className={styles.lineInfo}>
                    {line.productSlug ? (
                      <Link href={`/shop/${line.productSlug}`} className={styles.lineName}>
                        {line.productName}
                      </Link>
                    ) : (
                      <span className={styles.lineName}>Item</span>
                    )}
                    {line.variant ? (
                      <span className={styles.lineMeta}>
                        {line.variant.strength ? `${formatStrength(line.variant.strength)} · ` : ""}
                        {formSingular(line.variant.form)}
                      </span>
                    ) : (
                      <span className={styles.unavailable}>No longer available. Remove to continue.</span>
                    )}
                  </div>
                  <div className={styles.lineControls}>
                    <QuantityStepper
                      value={line.quantity}
                      onChange={(next) => setQuantity(line.variantId, next)}
                      disabled={!line.variant}
                      label="Quantity"
                      compact
                    />
                    <button type="button" className={styles.remove} onClick={() => removeItem(line.variantId)} aria-label="Remove line">
                      <SectionIcon name="trash" size={18} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {loadError && <p className={styles.unavailable}>{loadError}</p>}
          {lines.length > 0 && (
            <Link href="/shop" className={styles.addMore}>
              Add more compounds
            </Link>
          )}
        </section>

        <form className={styles.form} onSubmit={submit} aria-labelledby={`${id}-form`}>
          <h2 id={`${id}-form`} className={styles.formTitle}>
            Your details
          </h2>
          <div className={styles.fieldRow}>
            <label className={styles.field}>
              <span className={styles.label}>Name</span>
              <input className={styles.input} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
            </label>
            <label className={styles.field}>
              <span className={styles.label}>Organization or practice</span>
              <input className={styles.input} value={organization} onChange={(e) => setOrganization(e.target.value)} autoComplete="organization" required />
            </label>
          </div>
          <div className={styles.fieldRow}>
            <label className={styles.field}>
              <span className={styles.label}>Role</span>
              <select className={styles.input} value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span className={styles.label}>State</span>
              <input className={styles.input} value={region} onChange={(e) => setRegion(e.target.value)} autoComplete="address-level1" />
            </label>
          </div>
          <div className={styles.fieldRow}>
            <label className={styles.field}>
              <span className={styles.label}>Email</span>
              <input className={styles.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
            </label>
            <label className={styles.field}>
              <span className={styles.label}>Phone (optional)</span>
              <input className={styles.input} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" />
            </label>
          </div>
          <label className={styles.field}>
            <span className={styles.label}>Notes (optional)</span>
            <textarea
              className={`${styles.input} ${styles.textarea}`}
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Timing, documentation you need, anything else we should know."
            />
          </label>
          {/* Honeypot: hidden from people, filled by bots. */}
          <label className={styles.honeypot} aria-hidden="true">
            Website
            <input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
          </label>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          {hasUnavailable && <p className={styles.unavailable}>Remove unavailable lines before sending.</p>}

          <button type="submit" className={`button buttonAccent ${styles.submit}`} disabled={!canSubmit || submitting}>
            {submitting ? "Sending…" : "Send order request"}
          </button>
          <p className={styles.formNote}>
            Prefer to talk first?{" "}
            {BOOKING_URL ? (
              <a href={BOOKING_URL} target="_blank" rel="noopener noreferrer">
                Book a meeting
              </a>
            ) : (
              <Link href={CONTACT_PATH}>Contact us</Link>
            )}
            . Everything we supply is for laboratory research use only.
          </p>
        </form>
      </div>
    </main>
  );
}
