import Link from "next/link";
import Faq from "@/components/Faq";
import CatalogGrid from "@/components/catalog/CatalogGrid";
import { isSort } from "@/components/catalog/sort";
import { DEFAULT_VIEW, isView } from "@/components/catalog/view";
import Hero from "@/components/home/Hero";
import HowItWorks from "@/components/home/HowItWorks";
import QualitySection from "@/components/home/QualitySection";
import TrustRow from "@/components/home/TrustRow";
import { listProductsOrEmpty } from "@/lib/api";
import { findCategory } from "@/lib/categories";
import { SITE_FAQ } from "@/lib/faqContent";
import { findForm } from "@/lib/forms";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

const HOMEPAGE_FAQ_COUNT = 5;

// Homepage (modern, minimal, 2026-10-22): hero with a live catalog slice,
// the facts row, the WHOLE catalog as an order sheet (no featured or
// "popular" selection: lib/compliance.ts), how ordering works, quality,
// a few questions. The Pens | Vials toggle and the category pills filter
// the sheet in place (?form=, ?category=); ?view= switches sheet and grid.
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; category?: string; form?: string; view?: string }>;
}) {
  const params = await searchParams;
  const sort = isSort(params.sort) ? params.sort : "name";
  const category = findCategory(params.category);
  const form = findForm(params.form);
  const view = isView(params.view) ? params.view : DEFAULT_VIEW;
  const products = await listProductsOrEmpty({ sort });
  const configurations = products.reduce((sum, product) => sum + product.variants.length, 0);

  return (
    <main>
      <Hero products={products} configurations={configurations} />
      <TrustRow />
      <CatalogGrid
        products={products}
        title={
          <>
            The catalog, <em>by category.</em>
          </>
        }
        basePath="/"
        sort={sort}
        category={category}
        form={form}
        view={view}
      />
      <HowItWorks />
      <QualitySection />
      <section className={styles.faq}>
        <div className={`container ${styles.faqInner}`}>
          <div className={styles.sectionHead}>
            <span className="eyebrow">Questions</span>
            <h2>Asked often</h2>
          </div>
          <Faq entries={SITE_FAQ.slice(0, HOMEPAGE_FAQ_COUNT)} />
          <div className={styles.faqActions}>
            <Link href="/faq" className="button buttonAccentOutline">
              All questions
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
