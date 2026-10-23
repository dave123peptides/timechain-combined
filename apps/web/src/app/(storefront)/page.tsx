import Link from "next/link";
import Faq from "@/components/Faq";
import CatalogGrid from "@/components/catalog/CatalogGrid";
import { isSort } from "@/components/catalog/sort";
import FormatsSection from "@/components/home/FormatsSection";
import Hero from "@/components/home/Hero";
import HowItWorks from "@/components/home/HowItWorks";
import QualitySection from "@/components/home/QualitySection";
import RequestBand from "@/components/home/RequestBand";
import StatsStrip from "@/components/home/StatsStrip";
import { listProductsOrEmpty } from "@/lib/api";
import { findCategory } from "@/lib/categories";
import { SITE_FAQ } from "@/lib/faqContent";
import { findForm, formsIn } from "@/lib/forms";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

const HOMEPAGE_FAQ_COUNT = 5;

// Homepage (B2B redesign, 2026-10-22): hero, the live stats band, how
// ordering works, the WHOLE catalog as a grid (no featured or "popular"
// selection, which is also what lib/compliance.ts wants: with every
// product listed alphabetically there is no curated surface that could
// promote a GLP-class product), quality, the two formats, a few
// questions, and the closing request band. The Pens | Vials toggle and
// the category pills filter the grid in place (?form=, ?category=).
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; category?: string; form?: string }>;
}) {
  const params = await searchParams;
  const sort = isSort(params.sort) ? params.sort : "name";
  const category = findCategory(params.category);
  const form = findForm(params.form);
  const products = await listProductsOrEmpty({ sort });
  const configurations = products.reduce((sum, product) => sum + product.variants.length, 0);
  const formats = formsIn(products.flatMap((product) => product.variants)).length;

  return (
    <main data-flush-footer>
      <Hero />
      {products.length > 0 && <StatsStrip compounds={products.length} configurations={configurations} formats={formats} />}
      <HowItWorks />
      <CatalogGrid
        products={products}
        title={
          <>
            Every compound <em>we supply</em>
          </>
        }
        basePath="/"
        sort={sort}
        category={category}
        form={form}
      />
      <QualitySection />
      <FormatsSection />
      <section className={styles.faq}>
        <div className={`container ${styles.faqInner}`}>
          <div className={styles.sectionHead}>
            <span className="eyebrow">Questions</span>
            <h2>
              Asked <em>often.</em>
            </h2>
          </div>
          <Faq entries={SITE_FAQ.slice(0, HOMEPAGE_FAQ_COUNT)} />
          <div className={styles.faqActions}>
            <Link href="/faq" className="button buttonAccentOutline">
              All questions
            </Link>
          </div>
        </div>
      </section>
      <RequestBand />
    </main>
  );
}
