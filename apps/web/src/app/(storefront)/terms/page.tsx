import Link from "next/link";
import styles from "../legal.module.css";

export const metadata = { title: "Terms of Service" };

export default function TermsPage() {
  return (
    <main className={styles.wrap}>
      <span className={`eyebrow ${styles.eyebrow}`}>Policy</span>
      <h1>Terms of Service</h1>
      <p className={styles.updated}>Last updated October 22, 2026</p>

      <p>
        These terms govern your use of this site and any order you arrange with us after contacting us through
        it. By using this site or placing an order, you agree to these terms.
      </p>

      <h2>Eligibility</h2>
      <p>
        You must be at least 21 years old to use this site or place an order. By placing an order you confirm
        that you meet this requirement.
      </p>

      <h2>Products</h2>
      <p>
        All products are sold subject to our <Link href="/research-use-only">Research Use Only</Link> policy.
        Product descriptions, images, and pricing are subject to change without notice.
      </p>

      <h2>Orders</h2>
      <p>
        This site does not take payments. Orders are arranged directly with us after you contact us. Placing an
        order is an offer to purchase, subject to our acceptance. We may decline or cancel any order
        at our discretion, including where a product is no longer available or where required acknowledgments
        have not been given.
      </p>

      <h2>No warranty; limitation of liability</h2>
      <p>
        Products are provided &quot;as is&quot; for research use. To the fullest extent permitted by law,
        TimeChain disclaims all warranties and is not liable for any indirect, incidental, or consequential
        damages arising from the use of this site or any product purchased through it.
      </p>

      <h2>Changes</h2>
      <p>
        We may update these terms from time to time. The version in effect at the time you place an order is the
        version that applies to that order.
      </p>

      <h2>Contact</h2>
      <p>Questions about these terms can be sent to support@timechainpeptides.com.</p>
    </main>
  );
}
