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
import { isSupply } from "@/lib/supplies";
import ReconstitutionAddon from "./ReconstitutionAddon";
import VariantPicker from "./VariantPicker";
import ProductOverview from "./ProductOverview";
import ResearchAreas from "./ResearchAreas";
import RelatedProducts from "./RelatedProducts";
import ProductFaq from "./ProductFaq";
import ProductTabs, { LAB_REPORTS_TAB_ID, type ProductTab } from "./ProductTabs";
import LabReport from "./LabReport";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

export default async function ProductDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

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
  // Supplies drop out too: the ReconstitutionAddon block already offers
  // BAC water on every compound page. And a promotable product never
  // suggests a GLP-class one (lib/compliance.ts); GLP↔GLP cross-links are
  // research framing and stay.
  const resolvedPairs = product.content.pairs_with
    .map((pairSlug) => allProducts.find((p) => p.slug === pairSlug))
    .filter((p): p is (typeof allProducts)[number] => p !== undefined && p.slug !== product.slug && !isSupply(p));
  const relatedProducts = isPromotable(product) ? promotableOnly(resolvedPairs) : resolvedPairs;

  // The BAC water card renders on every compound PDP, but not on BAC
  // water's own page (it would offer the product to itself).
  const reconstitutionSupply = isSupply(product) ? undefined : allProducts.find((p) => isSupply(p));

  // The tabbed block under the buy box: About / Lab reports / Questions.
  // (Specifications moved into the buy box itself, Core-style.) About is
  // omitted rather than shown empty for a product with no authored copy;
  // Lab reports always renders, with the honest "on request" state when
  // nothing is held, so the tab a customer looks for is always there.
  const { content } = product;
  const hasAbout = Boolean(content.overview) || content.key_points.length > 0 || content.research_areas.length > 0;
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
    {
      id: LAB_REPORTS_TAB_ID,
      label: "Lab reports",
      badge: product.coas.length,
      content: <LabReport productName={product.name} productSlug={product.slug} coas={product.coas} />,
    },
    {
      id: "questions",
      label: "Questions",
      content: <ProductFaq faq={content.faq} hasCoas={product.coas.length > 0} />,
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
            sdsUrl={product.sds_url}
            supply={isSupply(product)}
          />
          <p className={styles.disclaimerNote}>For laboratory research use only. Not for human consumption.</p>
        </div>
      </div>

      <ReconstitutionAddon supply={reconstitutionSupply} />
      <ProductTabs tabs={tabs} />
      <RelatedProducts products={relatedProducts} />
    </main>
  );
}
