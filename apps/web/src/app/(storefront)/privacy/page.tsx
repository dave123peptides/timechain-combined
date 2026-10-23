import styles from "../legal.module.css";

export const metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <main className={styles.wrap}>
      <span className={`eyebrow ${styles.eyebrow}`}>Policy</span>
      <h1>Privacy Policy</h1>
      <p className={styles.updated}>Last updated October 22, 2026</p>

      <p>
        This policy describes what information we collect when you contact us or place an order with us, and how
        it&apos;s used.
      </p>

      <h2>Information we collect</h2>
      <p>
        When you contact us or book a meeting, we collect the details you provide: your name, email address, phone
        number and organization. When you place an order with us, we also collect a shipping address. If you book
        through our scheduling provider, that provider&apos;s own privacy policy applies to what you enter there.
      </p>

      <h2>How we use it</h2>
      <p>
        We use this information only to respond to your inquiry and to process, fulfill, and communicate with you
        about your order. Nothing more.
      </p>

      <h2>Sharing</h2>
      <p>
        We do not sell your personal information. We share order information only as necessary to fulfill an
        order, such as with shipping carriers.
      </p>

      <h2>Your requests</h2>
      <p>
        You can request access to, or deletion of, information associated with an inquiry or an order by
        contacting us at support@timechainpeptides.com.
      </p>
    </main>
  );
}
