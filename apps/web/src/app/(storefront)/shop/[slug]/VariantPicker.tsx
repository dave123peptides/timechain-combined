"use client";

import { useState } from "react";
import Link from "next/link";
import type { BulkDiscountTier, ProductCoa, Variant } from "@/lib/api";
import { formatMoney, formatStrength } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { distinctLabs, formatCoaDate, latestCoaForStrength } from "@/lib/coa";
import { findForm, formsIn } from "@/lib/forms";
import { useOrderRequest } from "@/lib/request-context";
import { BOOK_PATH, ORDERING_ENABLED, PRICING_VISIBLE } from "@/lib/site";
import { isSupply } from "@/lib/supplies";
import FormatNotice from "@/components/FormatNotice";
import QuantityStepper from "@/components/QuantityStepper";
import LabReportLink from "./LabReportLink";
import styles from "./page.module.css";

// Multi-quantity presets (B2B redesign, 2026-10-22): the quantities a
// practice or lab actually asks for. Typing any other number works too.
const QUANTITY_PRESETS = [5, 10, 25, 50, 100];
const DEFAULT_QUANTITY = 10;

// The grid's ?form= carries into the product page: open on that format
// when the product has it, otherwise on the first variant.
function pickInitial(variants: Variant[], initialForm?: string): string {
  const match = initialForm ? variants.find((v) => v.form === initialForm) : undefined;
  return (match ?? variants[0])?.id ?? "";
}

// The request builder below the product title: Format (when the compound
// ships as both a pen and a vial), Strength, Quantity, Add to request.
// No price unless pricing is on (lib/site.ts) and the API sent one. Spec
// rows are derived from data the catalog holds or from a constraint
// enforced in code (SELLABLE_FORMS on the API's catalog model). No
// purity, no storage or shelf-life figures, no internal SKU. With
// ordering on the old Add to Cart returns in place of the request button.
export default function VariantPicker({
  variants,
  coas,
  productName,
  productSlug,
  sdsUrl,
  initialForm,
}: {
  variants: Variant[];
  bulkTiers: BulkDiscountTier[];
  coas: ProductCoa[];
  productName: string;
  productSlug: string;
  sdsUrl: string | null;
  initialForm?: string;
}) {
  const [selectedId, setSelectedId] = useState(() => pickInitial(variants, initialForm));
  const [quantity, setQuantity] = useState(DEFAULT_QUANTITY);
  const [justAdded, setJustAdded] = useState(false);
  const { addItem: addToCart, openDrawer: openCart } = useCart();
  const { addItem, openDrawer } = useOrderRequest();

  const selected = variants.find((v) => v.id === selectedId) ?? variants[0];
  if (!selected) return null;

  const forms = formsIn(variants);
  const selectedForm = findForm(selected.form);
  const sameForm = variants.filter((v) => v.form === selected.form);
  const strengthText = selected.strength ? formatStrength(selected.strength) : selected.format;
  const formText = isSupply(productSlug) ? "Sterile diluent in a sealed vial" : (selectedForm?.shipsAs ?? selected.format);
  const coasForStrength = coas.filter((coa) => coa.strength === selected.strength);
  const latestForStrength = latestCoaForStrength(coas, selected.strength);
  const showPrice = PRICING_VISIBLE && selected.price_cents !== null;

  // Switching format keeps the strength where both offer it, otherwise
  // lands on that format's first variant.
  const selectForm = (key: string) => {
    const ofForm = variants.filter((v) => v.form === key);
    const next = ofForm.find((v) => v.strength === selected.strength) ?? ofForm[0];
    if (next) setSelectedId(next.id);
  };

  const handleAdd = () => {
    if (ORDERING_ENABLED) {
      addToCart(selected.id, quantity);
      openCart();
      return;
    }
    addItem(selected.id, quantity);
    setJustAdded(true);
    openDrawer();
  };

  return (
    <div className={styles.builder}>
      {showPrice && <span className={styles.priceNow}>{formatMoney(selected.price_cents as number)}</span>}

      {forms.length > 1 && (
        <>
          <span className={styles.fieldLabel}>Format</span>
          <div className={styles.variantOptions} role="group" aria-label="Format">
            {forms.map((form) => (
              <button
                key={form.key}
                type="button"
                className={`${styles.variantOption} ${form.key === selected.form ? styles.variantOptionSelected : ""}`}
                onClick={() => selectForm(form.key)}
                aria-pressed={form.key === selected.form}
              >
                {form.singular}
              </button>
            ))}
          </div>
        </>
      )}

      {sameForm.length > 1 && (
        <>
          <span className={styles.fieldLabel}>Strength</span>
          <div className={styles.variantOptions} role="group" aria-label="Strength">
            {sameForm.map((variant) => (
              <button
                key={variant.id}
                type="button"
                className={`${styles.variantOption} ${variant.id === selectedId ? styles.variantOptionSelected : ""}`}
                onClick={() => setSelectedId(variant.id)}
                aria-pressed={variant.id === selectedId}
              >
                {variant.strength ? formatStrength(variant.strength) : variant.format}
              </button>
            ))}
          </div>
        </>
      )}

      <span className={styles.fieldLabel}>Quantity</span>
      <div className={styles.quantityRow}>
        <QuantityStepper value={quantity} onChange={setQuantity} label="Quantity" />
        <div className={styles.presets} role="group" aria-label="Quantity presets">
          {QUANTITY_PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              className={`${styles.preset} ${quantity === preset ? styles.presetActive : ""}`}
              onClick={() => setQuantity(preset)}
              aria-pressed={quantity === preset}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.buyRow}>
        <button type="button" className={`button buttonAccent ${styles.addButton}`} onClick={handleAdd}>
          {ORDERING_ENABLED ? "Add to Cart" : justAdded ? "Added. Add more" : "Add to request"}
        </button>
      </div>
      <p className={styles.builderNote}>
        {ORDERING_ENABLED ? (
          "Quantity discounts apply at checkout."
        ) : (
          <>
            Build your list, then send it with your details. We reply by email with availability, documentation and
            pricing for your quantities. <Link href={BOOK_PATH}>Prefer to talk first? Book a meeting.</Link>
          </>
        )}
      </p>

      <dl className={styles.specs}>
        <div className={styles.specRow}>
          <dt>Strength</dt>
          <dd>{strengthText}</dd>
        </div>
        <div className={styles.specRow}>
          <dt>Contents</dt>
          <dd>{productName}</dd>
        </div>
        <div className={styles.specRow}>
          <dt>Form</dt>
          <dd>{formText}</dd>
        </div>
        {(coas.length > 0 || sdsUrl) && (
          <div className={styles.specRow}>
            <dt>{coas.length > 0 ? "Certificates" : "Documents"}</dt>
            <dd>
              {coas.length > 0 && (
                <LabReportLink className={styles.coaLink}>
                  {latestForStrength
                    ? `${coasForStrength.length} on file for ${strengthText} · latest ${formatCoaDate(latestForStrength.issued_on)} · ${distinctLabs(coasForStrength).join(", ")}`
                    : `${coas.length} on file (other strengths)`}
                </LabReportLink>
              )}
              {sdsUrl && (
                <>
                  {coas.length > 0 && " · "}
                  <a className={styles.coaLink} href={sdsUrl} target="_blank" rel="noopener noreferrer">
                    Safety Data Sheet
                  </a>
                </>
              )}
            </dd>
          </div>
        )}
      </dl>

      <FormatNotice form={selected.form} productSlug={productSlug} />
    </div>
  );
}
