"use client";

import { useId, useState } from "react";
import styles from "./page.module.css";

const SUPPORT_EMAIL = "support@timechainpeptides.com";

const TOPICS = ["Document request", "Order question", "Product specification", "Other"] as const;

// The Core-reference contact form, without a backend: there is no email
// provider wired into this codebase (no SMTP, SendGrid, Resend or SES)
// and no contact_messages table, so submitting builds a mailto: URL and
// hands it to the visitor's own mail app with everything pre-filled.
// Nothing is stored or posted by this site. If a real form is wanted
// later it needs a provider decision, and it must POST to a route
// handler — never a server action, which 500s in Next 15.5 production
// builds.
export default function ContactForm() {
  const id = useId();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [topic, setTopic] = useState<(typeof TOPICS)[number]>(TOPICS[0]);
  const [reference, setReference] = useState("");
  const [message, setMessage] = useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const subject = `[${topic}] ${name.trim() || "Website enquiry"}`;
    const body = [
      message.trim(),
      "",
      reference.trim() ? `Order / lot number: ${reference.trim()}` : null,
      name.trim() ? `Name: ${name.trim()}` : null,
      email.trim() ? `Reply to: ${email.trim()}` : null,
    ]
      .filter((line) => line !== null)
      .join("\n");
    window.location.href = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <div className={styles.fieldRow}>
        <label className={styles.field}>
          <span className={styles.label}>Name</span>
          <input className={styles.input} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        </label>
        <label className={styles.field}>
          <span className={styles.label}>Your email</span>
          <input
            className={styles.input}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </label>
      </div>
      <div className={styles.fieldRow}>
        <label className={styles.field}>
          <span className={styles.label}>Topic</span>
          <select className={styles.input} value={topic} onChange={(e) => setTopic(e.target.value as (typeof TOPICS)[number])}>
            {TOPICS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          <span className={styles.label}>Order or lot number (optional)</span>
          <input className={styles.input} value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
      </div>
      <label className={styles.field}>
        <span className={styles.label}>Message</span>
        <textarea
          id={`${id}-message`}
          className={`${styles.input} ${styles.textarea}`}
          rows={6}
          required
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </label>
      <button type="submit" className="button buttonPill buttonAccent">
        Open in my mail app
      </button>
      <p className={styles.formNote}>
        Sending opens your own email app with this message addressed to {SUPPORT_EMAIL}. Nothing is stored on this
        site.
      </p>
      <noscript>
        <p className={styles.formNote}>
          Email us directly at <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      </noscript>
    </form>
  );
}
