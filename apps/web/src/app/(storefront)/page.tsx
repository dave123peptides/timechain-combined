import Link from "next/link";
import Faq from "@/components/Faq";
import CatalogGrid from "@/components/catalog/CatalogGrid";
import { isSort } from "@/components/catalog/sort";
import HomeHero from "@/components/home/HomeHero";
import TrustStrip from "@/components/home/TrustStrip";
import { listProductsOrEmpty } from "@/lib/api";
import { SITE_FAQ } from "@/lib/faqContent";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

const HOMEPAGE_FAQ_COUNT = 6;

// Core-reference homepage (David, 9/4): hero, the black trust strip, then
// the WHOLE catalog as a grid — no featured/"popular" selection, which is
// also what lib/compliance.ts wants: with every product listed
// alphabetically there is no curated surface that could promote a
// GLP-class product. The standards/pipeline/purity content that used to
// fill this page lives on /about now.
export default async function Home({ searchParams }: { searchParams: Promise<{ sort?: string }> }) {
  const params = await searchParams;
  const sort = isSort(params.sort) ? params.sort : "name";
  const products = await listProductsOrEmpty({ sort });

  return (
    <main>
      <HomeHero />
      <TrustStrip />
      <CatalogGrid products={products} title="Research Peptides For Sale" basePath="/" sort={sort} />
      <section className={styles.faq}>
        <div className={`container ${styles.faqInner}`}>
          <div className={styles.sectionHead}>
            <span className="eyebrow">Questions</span>
            <h2>Frequently Asked</h2>
          </div>
          {/* A subset here; /faq carries the full list. Both read the same
              constant so they can never disagree. */}
          <Faq entries={SITE_FAQ.slice(0, HOMEPAGE_FAQ_COUNT)} />
          <div className={styles.faqActions}>
            <Link href="/faq" className="button buttonPill buttonAccentOutline">
              All questions
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
