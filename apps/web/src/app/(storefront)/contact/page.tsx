import SectionIcon from "@/components/SectionIcon";
import ContactForm from "./ContactForm";
import styles from "./page.module.css";

export const metadata = { title: "Contact | TimeChain" };

const SUPPORT_EMAIL = "support@timechainpeptides.com";

// Core-reference contact page (David, 9/4): two panels — a dark one with
// the form, an accent one with the ways to reach us. No phone number and
// no hours: neither exists. The form has no backend (see ContactForm);
// email is still the only channel, it just arrives pre-addressed.
export default function ContactPage() {
  return (
    <main>
      <section className={styles.panels}>
        <div className={styles.dark}>
          <div className={styles.panelInner}>
            <h1 className={styles.title}>Get in touch with us.</h1>
            <p className={styles.lede}>
              You can email us directly at <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>, or fill out the
              form below.
            </p>
            <ContactForm />
          </div>
        </div>

        <div className={styles.accent}>
          <div className={styles.panelInner}>
            <h2 className={styles.accentTitle}>Email reaches a person, not a queue.</h2>
            <p className={styles.accentLede}>
              Questions about product specifications, documentation, and orders are answered by the people who run
              the catalog.
            </p>
            <ul className={styles.rows}>
              <li className={styles.row}>
                <span className={styles.rowIcon}>
                  <SectionIcon name="mail" size={22} />
                </span>
                <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
              </li>
              <li className={styles.row}>
                <span className={styles.rowIcon}>
                  <SectionIcon name="map" size={22} />
                </span>
                <span>
                  Timechain Ventures LLC, d/b/a Timechain Peptides
                  <br />
                  Florida, USA
                </span>
              </li>
              <li className={styles.row}>
                <span className={styles.rowIcon}>
                  <SectionIcon name="document" size={22} />
                </span>
                <span>
                  For a document request, name the product and the lot or order number so we can pull the right
                  batch paperwork. For an order question, the order number alone is enough.
                </span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <div className={styles.footnote}>
        <p>
          We can answer questions about product specifications, documentation, and orders. We cannot advise on
          dosing or on any human or veterinary application — everything we supply is for laboratory and research use
          only.
        </p>
      </div>
    </main>
  );
}
