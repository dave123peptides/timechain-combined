import styles from "../legal.module.css";

export const metadata = { title: "Privacy Policy | TCP" };

export default function PrivacyPage() {
  return (
    <main className={styles.wrap}>
      <span className={`eyebrow ${styles.eyebrow}`}>Policy</span>
      <h1>Privacy Policy</h1>
      <p className={styles.updated}>Last updated August 13, 2026</p>

      <p>This policy describes what information we collect when you place an order, and how it&apos;s used.</p>

      <h2>Information we collect</h2>
      <p>When you place an order, we collect your email address and shipping address.</p>

      <h2>How we use it</h2>
      <p>
        We use this information only to process, fulfill, and communicate with you about your order — nothing
        more.
      </p>

      <h2>Sharing</h2>
      <p>
        We do not sell your personal information. We share order information only as necessary to fulfill an
        order, such as with shipping carriers.
      </p>

      <h2>Your requests</h2>
      <p>
        You can request access to, or deletion of, information associated with an order by contacting us with
        your order number.
      </p>
    </main>
  );
}
