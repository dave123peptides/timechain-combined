import Link from "next/link";
import { listCoasOrEmpty, listProductsOrEmpty } from "@/lib/api";
import type { CoaCardGroup } from "@/lib/coa";
import { distinctLabs, formatCoaDate, groupCoasByStrength, strengthLabel } from "@/lib/coa";
import CoaIndex from "./CoaIndex";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Certificates of Analysis | TCP" };

const SUPPORT_EMAIL = "support@timechainpeptides.com";

// Central certificate index (the Real Peptides /coas pattern): every
// published third-party certificate for every sellable product, one card
// per product and strength, searchable by name, strength, lot or
// verification code. The numbers in the header are counts of documents
// held — nothing here summarises what the documents say. Products with no
// certificate are listed underneath in the same honest "on request" state
// this page showed for the whole catalog before the certificates arrived.
export default async function CoaPage() {
  const [products, entries] = await Promise.all([listProductsOrEmpty(), listCoasOrEmpty()]);

  const groups: CoaCardGroup[] = entries.flatMap((entry) =>
    groupCoasByStrength(entry.coas).map((group) => {
      const label = strengthLabel(group.strength);
      return {
        key: `${entry.slug}:${group.strength ?? ""}`,
        title: entry.name,
        subtitle: label,
        productSlug: entry.slug,
        coas: group.coas,
      };
    })
  );
  const allCoas = entries.flatMap((entry) => entry.coas);
  const labs = distinctLabs(allCoas);
  const latest = allCoas.reduce<string | null>(
    (newest, coa) => (newest === null || coa.issued_on > newest ? coa.issued_on : newest),
    null
  );
  const onRequest = products.filter((product) => product.coa_count === 0);

  return (
    <main className={`container ${styles.page}`}>
      <div className={styles.hero}>
        <div className={styles.heroText}>
          <span className="eyebrow">
            Verification{entries.length > 0 ? ` · ${entries.length} compounds certified` : ""}
          </span>
          <h1>Certificates of Analysis</h1>
          <p className={styles.lede}>
            Every certificate below is a third-party lab report for one lot of one strength, issued by the
            laboratory to our supplier. Each opens the lab&apos;s own copy in a new tab and carries a verification
            code you can check with the lab directly. We link to the document rather than quoting a purity figure
            from it.
          </p>
        </div>
        {allCoas.length > 0 && (
          <dl className={styles.stats}>
            <div>
              <dt>Certificates on file</dt>
              <dd>{allCoas.length}</dd>
            </div>
            <div>
              <dt>Compounds</dt>
              <dd>{entries.length}</dd>
            </div>
            <div>
              <dt>Latest certificate</dt>
              <dd>{latest ? formatCoaDate(latest) : "—"}</dd>
            </div>
            <div>
              <dt>Laboratory</dt>
              <dd>{labs.join(", ")}</dd>
            </div>
          </dl>
        )}
      </div>

      {products.length === 0 && entries.length === 0 ? (
        <p className={styles.empty}>The catalog is unavailable right now — please check back shortly.</p>
      ) : (
        <>
          <CoaIndex groups={groups} />

          {onRequest.length > 0 && (
            <section className={styles.onRequest}>
              <h2 className={styles.onRequestTitle}>Available on request</h2>
              <p className={styles.onRequestLede}>
                No certificate is published yet for the products below. Email{" "}
                <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with the product and lot number and
                we&apos;ll send the paperwork for the batch you received.
              </p>
              <ul className={styles.onRequestList}>
                {onRequest.map((product) => (
                  <li key={product.slug}>
                    <Link href={`/shop/${product.slug}`}>{product.name}</Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className={styles.footnote}>
            Certificates are issued per lot. If the lot printed on your pen isn&apos;t listed, email{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> with the lot number and we&apos;ll send its
            certificate.
          </p>
        </>
      )}
    </main>
  );
}
