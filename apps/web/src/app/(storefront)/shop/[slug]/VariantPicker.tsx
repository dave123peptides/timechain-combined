"use client";

import { useId, useRef, useState } from "react";
import Link from "next/link";
import type { BulkDiscountTier, ProductCoa, Variant } from "@/lib/api";
import { discountedUnitPriceCents, formatMoney, formatStrength } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { distinctLabs, formatCoaDate, latestCoaForStrength } from "@/lib/coa";
import { findForm, formsIn } from "@/lib/forms";
import { ORDERING_ENABLED, contactHref } from "@/lib/site";
import { isSupply } from "@/lib/supplies";
import FormatNotice from "@/components/FormatNotice";
import QuantityStepper from "@/components/QuantityStepper";
import LabReportLink from "./LabReportLink";
import StickyBuyBar from "./StickyBuyBar";
import styles from "./page.module.css";

// [min, max] quantity range per row, derived from the ascending tier
// list; max is undefined for the top ("20+") row.
function bulkPricingRows(bulkTiers: BulkDiscountTier[]) {
  const breaks = [{ min: 1, percentOff: 0 }, ...bulkTiers.map((t) => ({ min: t.min_quantity, percentOff: t.percent_off }))];
  return breaks.map((row, i) => ({ ...row, max: breaks[i + 1] ? breaks[i + 1].min - 1 : undefined }));
}

function rangeLabel(row: { min: number; max?: number }): string {
  return row.max === undefined ? `${row.min}+` : `${row.min} – ${row.max}`;
}

// The grid's ?form= carries into the product page: open on that format
// when the product has it, otherwise on the first (cheapest) variant.
function pickInitial(variants: Variant[], initialForm?: string): string {
  const match = initialForm ? variants.find((v) => v.form === initialForm) : undefined;
  return (match ?? variants[0])?.id ?? "";
}

// The buy box below the product title (Core reference, 9/4): price, a
// Format picker when the compound ships as both a pen and a vial (one
// product row per compound, David 2026-10-22), the strengths of the
// chosen format, the call to action, a plain spec list and the format
// notice. Everything here keys off the selected variant, which is why
// one client component owns the lot.
//
// The call to action depends on lib/site.ts: in inquiry mode (the
// default) it is a link to the contact page naming this exact variant;
// with ordering on it is quantity + Add to Cart, the bulk-discount table
// and the sticky buy bar, as before.
//
// Spec rows are derived from data the catalog actually holds or from a
// constraint enforced in code (the form: SELLABLE_FORMS on the API's
// catalog model). No purity, no storage or shelf-life figures, no
// internal SKU: a spec list is exactly where an unconfirmed number would
// read as a promise.
export default function VariantPicker({
  variants,
  bulkTiers,
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
  const [quantity, setQuantity] = useState(1);
  const tierGroup = useId();
  // The desktop buy bar watches this button to know when it has scrolled
  // out of view. It observes the button itself rather than an empty
  // marker div: a zero-height element is unreliable to observe.
  const addButtonRef = useRef<HTMLButtonElement>(null);
  const { addItem, openDrawer } = useCart();

  const selected = variants.find((v) => v.id === selectedId) ?? variants[0];
  if (!selected) return null;

  const forms = formsIn(variants);
  const selectedForm = findForm(selected.form);
  const sameForm = variants.filter((v) => v.form === selected.form);
  const pricingRows = bulkPricingRows(bulkTiers);
  const strengthText = selected.strength ? formatStrength(selected.strength) : selected.format;
  const formText = isSupply(productSlug) ? "Sterile diluent in a sealed vial" : (selectedForm?.shipsAs ?? selected.format);
  const coasForStrength = coas.filter((coa) => coa.strength === selected.strength);
  const latestForStrength = latestCoaForStrength(coas, selected.strength);

  // Switching format keeps the strength where both formats offer it,
  // otherwise lands on that format's first (cheapest) variant.
  const selectForm = (key: string) => {
    const ofForm = variants.filter((v) => v.form === key);
    const next = ofForm.find((v) => v.strength === selected.strength) ?? ofForm[0];
    if (next) setSelectedId(next.id);
  };

  const handleAdd = () => {
    addItem(selected.id, quantity);
    openDrawer();
  };

  return (
    <div>
      <span className={styles.priceNow}>{formatMoney(selected.price_cents)}</span>

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

      {ORDERING_ENABLED ? (
        // Quantity + Add to Cart sit directly under the price so they are
        // on the first screen without scrolling (David, 9/5).
        <div className={styles.buyRow}>
          <QuantityStepper value={quantity} onChange={setQuantity} label="Quantity" />
          <button
            ref={addButtonRef}
            type="button"
            className={`button buttonPill buttonAccentOutline ${styles.desktopAddButton} ${styles.addButton}`}
            onClick={handleAdd}
          >
            Add to Cart
          </button>
        </div>
      ) : (
        <div className={styles.inquiry}>
          <Link href={contactHref(productSlug, selected.id)} className={`button buttonPill buttonAccent ${styles.inquiryButton}`}>
            Contact us about this product
          </Link>
          <p className={styles.inquiryNote}>
            Orders are arranged directly with us. Book a meeting or email, and we go over formats, quantities and
            documentation.
          </p>
        </div>
      )}

      {ORDERING_ENABLED && pricingRows.length > 1 && (
        <div className={styles.bulkPricing} role="radiogroup" aria-label="Quantity pricing tier">
          <table className={styles.bulkTable}>
            <thead>
              <tr>
                <th scope="col">
                  <span className="sr-only">Selected</span>
                  <span aria-hidden="true">✓</span>
                </th>
                <th scope="col">Quantity</th>
                <th scope="col">Discount</th>
                <th scope="col">Price</th>
              </tr>
            </thead>
            <tbody>
              {pricingRows.map((row) => {
                const active = quantity >= row.min && (row.max === undefined || quantity <= row.max);
                const rowId = `${tierGroup}-${row.min}`;
                return (
                  <tr key={row.min} className={active ? styles.bulkRowActive : undefined}>
                    <td>
                      {/* Checked state is DERIVED from the quantity, so the
                          stepper and the sticky bar move it too; picking a
                          row sets the quantity to that tier's minimum. */}
                      <input
                        type="radio"
                        id={rowId}
                        name={tierGroup}
                        className={styles.bulkRadio}
                        checked={active}
                        onChange={() => setQuantity(row.min)}
                        aria-label={`${rangeLabel(row)} units`}
                      />
                    </td>
                    <td>
                      <label htmlFor={rowId}>{rangeLabel(row)}</label>
                    </td>
                    <td>{row.percentOff > 0 ? `${row.percentOff}%` : "—"}</td>
                    <td className={styles.bulkPrice}>{formatMoney(discountedUnitPriceCents(selected.price_cents, row.percentOff))}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

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
        {/* Certificates row only once a product holds them (David,
            2026-09-05): nothing on the page mentions COAs until they are
            loaded. */}
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

      {ORDERING_ENABLED && (
        <StickyBuyBar
          watchRef={addButtonRef}
          priceCents={selected.price_cents}
          quantity={quantity}
          onQuantityChange={setQuantity}
          onAdd={handleAdd}
        />
      )}
    </div>
  );
}
