import Link from "next/link";
import SectionIcon from "@/components/SectionIcon";
import { formatStrength, getProduct, type ProductDetail } from "@/lib/api";
import { findForm } from "@/lib/forms";
import { BOOKING_URL, SUPPORT_EMAIL } from "@/lib/site";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Contact" };

// The site's one call to action (David, 2026-10-22): no payments, no
// checkout. A visitor browses the catalog, then books a short meeting
// here. The Book a meeting button goes to the scheduling page David
// supplies (NEXT_PUBLIC_BOOKING_URL); until that is set the button is an
// email instead, so the page never dead-ends. Two panels, as on the
// vial site's contact page (Core reference, 9/4): dark with the action,
// accent with the ways to reach us. No phone number and no hours:
// neither exists.
//
// ?product=<slug>&variant=<id> (from every Contact us button on a card
// or product page) names what the visitor was looking at, on the page
// and in the email subject.
export default async function ContactPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string; variant?: string }>;
}) {
  const { product: slug, variant: variantId } = await searchParams;

  let product: ProductDetail | null = null;
  if (slug) {
    try {
      product = await getProduct(slug);
    } catch {
      // Unknown slug or API down: the page still works, just without the
      // "asking about" line.
      product = null;
    }
  }
  const variant = product?.variants.find((v) => v.id === variantId);
  const asking = product
    ? [
        product.name,
        variant?.strength ? formatStrength(variant.strength) : null,
        variant ? (findForm(variant.form)?.singular ?? variant.format) : null,
      ]
        .filter(Boolean)
        .join(", ")
    : null;
  const subject = asking ? `Meeting request: ${asking}` : "Meeting request";
  const mailto = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}`;

  return (
    <main data-flush-footer>
      <section className={styles.panels}>
        <div className={styles.dark}>
          <div className={styles.panelInner}>
            <h1 className={styles.title}>Let&apos;s talk about what you need.</h1>
            <p className={styles.lede}>
              We supply research peptides in pre-filled auto-injector pens and lyophilized vials. This site takes
              no orders directly. Book a short meeting and we go over formats, quantities and documentation for
              your clinic or laboratory, then arrange the order with you.
            </p>
            {asking && (
              <p className={styles.asking}>
                Asking about <strong>{asking}</strong>
                {product && (
                  <>
                    {" "}
                    (<Link href={`/shop/${product.slug}`}>view product</Link>)
                  </>
                )}
              </p>
            )}
            <div className={styles.actions}>
              {BOOKING_URL ? (
                <a href={BOOKING_URL} target="_blank" rel="noopener noreferrer" className="button buttonPill buttonAccent">
                  Book a meeting
                </a>
              ) : (
                <a href={mailto} className="button buttonPill buttonAccent">
                  Email us to book a meeting
                </a>
              )}
              {BOOKING_URL && (
                <a href={mailto} className={styles.secondary}>
                  or email {SUPPORT_EMAIL}
                </a>
              )}
            </div>
          </div>
        </div>

        <div className={styles.accent}>
          <div className={styles.panelInner}>
            <h2 className={styles.accentTitle}>A person answers, not a queue.</h2>
            <p className={styles.accentLede}>
              Questions about formats, specifications, documentation and ordering are answered by the people who
              run the catalog.
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
                  TimeChain Peptides
                  <br />
                  Florida, USA
                </span>
              </li>
              <li className={styles.row}>
                <span className={styles.rowIcon}>
                  <SectionIcon name="document" size={22} />
                </span>
                <span>
                  For a document request, name the product and the lot number so we can pull the right batch
                  paperwork.
                </span>
              </li>
            </ul>
            <p className={styles.accentNote}>
              We can&apos;t advise on dosing or on any human or veterinary application. Everything we supply is for
              laboratory and research use only.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
