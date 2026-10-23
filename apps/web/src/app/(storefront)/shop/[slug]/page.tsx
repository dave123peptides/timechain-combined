import { notFound } from "next/navigation";
import {
  ApiError,
  getBulkDiscountTiers,
  getProduct,
  isUnreachable,
  listProducts,
  type BulkDiscountTier,
  type ProductSummary,
} from "@/lib/api";
import Breadcrumb from "@/components/Breadcrumb";
import ProductGallery from "@/components/ProductGallery";
import { isPromotable, promotableOnly } from "@/lib/compliance";
import VariantPicker from "./VariantPicker";
import ProductOverview from "./ProductOverview";
import ResearchAreas from "./ResearchAreas";
import RelatedProducts from "./RelatedProducts";
import ProductFaq from "./ProductFaq";
import ProductTabs, { LAB_REPORTS_TAB_ID, type ProductTab } from "./ProductTabs";
import LabReport from "./LabReport";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

export default async function ProductDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ form?: string }>;
}) {
  const { slug } = await params;
  // From a grid narrowed to one format (?form=): the picker opens on it.
  const { form } = await searchParams;

  let product;
  try {
    product = await getProduct(slug);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    // API down / unreachable: a product page has nothing meaningful to
    // show without prices and variants — present the standard 404 rather
    // than a crash page.
    if (isUnreachable(err)) {
      notFound();
    }
    throw err;
  }

  let bulkTiers: BulkDiscountTier[];
  let allProducts: ProductSummary[];
  try {
    [bulkTiers, allProducts] = await Promise.all([getBulkDiscountTiers(), listProducts()]);
  } catch {
    // Secondary data only (bulk table, related products) — degrade, don't crash.
    bulkTiers = [];
    allProducts = [];
  }

  // Resolved against the live sellable catalog, not trusted as-is — a
  // pairs_with slug that's out of stock or renamed just silently drops
  // instead of breaking the page (see ProductContentResponse's docstring).
  // A promotable product never suggests a GLP-class one
  // (lib/compliance.ts); GLP↔GLP cross-links are research framing and stay.
  const resolvedPairs = product.content.pairs_with
    .map((pairSlug) => allProducts.find((p) => p.slug === pairSlug))
    .filter((p): p is (typeof allProducts)[number] => p !== undefined && p.slug !== product.slug);
  const relatedProducts = isPromotable(product) ? promotableOnly(resolvedPairs) : resolvedPairs;

  // The tabbed block under the buy box: About / Lab reports / Questions.
  // (Specifications moved into the buy box itself, Core-style.) About is
  // omitted rather than shown empty for a product with no authored copy.
  // Lab reports is omitted until a product actually holds certificates
  // (David, 2026-09-05: pen COAs exist but aren't loaded yet — the tab
  // returns by itself once sync_coas has run), so nothing on the page
  // talks about certificates in the meantime.
  const { content } = product;
  const hasAbout = Boolean(content.overview) || content.key_points.length > 0 || content.research_areas.length > 0;
  const hasCoas = product.coas.length > 0;
  const tabs: ProductTab[] = [
    ...(hasAbout
      ? [
          {
            id: "about",
            label: "About",
            content: (
              <>
                <ProductOverview name={product.name} content={content} />
                <ResearchAreas content={content} />
              </>
            ),
          },
        ]
      : []),
    ...(hasCoas
      ? [
          {
            id: LAB_REPORTS_TAB_ID,
            label: "Lab reports",
            badge: product.coas.length,
            content: <LabReport productName={product.name} productSlug={product.slug} coas={product.coas} />,
          },
        ]
      : []),
    {
      id: "questions",
      label: "Questions",
      content: <ProductFaq faq={content.faq} hasCoas={hasCoas} />,
    },
  ];

  return (
    <main className={`container ${styles.page}`}>
      <Breadcrumb items={[{ label: "Home", href: "/" }, { label: "Shop", href: "/shop" }, { label: product.name }]} />
      <div className={styles.layout}>
        <div className={styles.imageWrap}>
          <ProductGallery images={product.images} name={product.name} />
        </div>
        <div>
          <h1 className={styles.name}>{product.name}</h1>
          {product.description && <p className={styles.description}>{product.description}</p>}
          <VariantPicker
            variants={product.variants}
            bulkTiers={bulkTiers}
            coas={product.coas}
            productName={product.name}
            productSlug={product.slug}
            sdsUrl={product.sds_url}
            initialForm={form}
          />
          <p className={styles.disclaimerNote}>For laboratory research use only. Not for human consumption.</p>
        </div>
      </div>

      <ProductTabs tabs={tabs} />
      <RelatedProducts products={relatedProducts} />
    </main>
  );
}
