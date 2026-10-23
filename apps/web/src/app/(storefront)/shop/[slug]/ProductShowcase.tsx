"use client";

import { useCallback, useState } from "react";
import type { BulkDiscountTier, ProductDetail } from "@/lib/api";
import { imagesForForm } from "@/lib/forms";
import ProductGallery from "@/components/ProductGallery";
import VariantPicker from "./VariantPicker";
import styles from "./page.module.css";

// The top of the product page: gallery left, name and picker right. One
// client component so the gallery can follow the picker's format: a pen
// render while Pen is selected, the vial photo for Vial (David,
// 2026-10-23). The gallery is keyed on the format so it restarts on the
// first matching photo when the format changes.
export default function ProductShowcase({
  product,
  bulkTiers,
  initialForm,
}: {
  product: ProductDetail;
  bulkTiers: BulkDiscountTier[];
  initialForm?: string;
}) {
  const [form, setForm] = useState<string | null>(initialForm ?? null);
  const onFormChange = useCallback((next: string | null) => setForm(next), []);
  const images = imagesForForm(product.images, form);

  return (
    <div className={styles.layout}>
      <div className={styles.imageWrap}>
        <ProductGallery key={form ?? "all"} images={images} name={product.name} />
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
          initialForm={initialForm}
          onFormChange={onFormChange}
        />
        <p className={styles.disclaimerNote}>For laboratory research use only. Not for human consumption.</p>
      </div>
    </div>
  );
}
