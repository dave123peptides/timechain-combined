"use client";

import { useId, useRef, useState } from "react";
import type { BulkDiscountTier, ProductCoa, Variant } from "@/lib/api";
import { discountedUnitPriceCents, formatMoney, formatStrength } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { distinctLabs, formatCoaDate, latestCoaForStrength } from "@/lib/coa";
import FormatNotice from "@/components/FormatNotice";
import QuantityStepper from "@/components/QuantityStepper";
import LabReportLink from "./LabReportLink";
import StickyBuyBar from "./StickyBuyBar";
import styles from "./page.module.css";

// [min, max] quantity range per row, derived from the ascending tier
// list — max is undefined for the top ("20+") row.
function bulkPricingRows(bulkTiers: BulkDiscountTier[]) {
  const breaks = [{ min: 1, percentOff: 0 }, ...bulkTiers.map((t) => ({ min: t.min_quantity, percentOff: t.percent_off }))];
  return breaks.map((row, i) => ({ ...row, max: breaks[i + 1] ? breaks[i + 1].min - 1 : undefined }));
}

function rangeLabel(row: { min: number; max?: number }): string {
  return row.max === undefined ? `${row.min}+` : `${row.min} – ${row.max}`;
}

// The buy box below the product title (Core reference, 9/4): price,
// strength, a plain spec list, the Certificate of Analysis pill, the
// bulk-discount table with a radio per tier, then quantity + Add to Cart.
// Everything here keys off the selected strength, which is why one
// client component owns the lot.
//
// Spec rows are derived from data the catalog actually holds or from a
// constraint enforced in code (the lyophilized format:
// ProductVariant._validate_is_sellable rejects anything else). No
// purity, no storage or shelf-life figures, no internal SKU — a spec
// list is exactly where an unconfirmed number would read as a promise.
export default function VariantPicker({
  variants,
  bulkTiers,
  coas,
  productName,
  sdsUrl,
  supply,
}: {
  variants: Variant[];
  bulkTiers: BulkDiscountTier[];
  coas: ProductCoa[];
  productName: string;
  sdsUrl: string | null;
  supply: boolean;
}) {
  const [selectedId, setSelectedId] = useState(variants[0]?.id ?? "");
  const [quantity, setQuantity] = useState(1);
  const tierGroup = useId();
  // The desktop buy bar watches this button to know when it has scrolled
  // out of view. It observes the button itself rather than an empty
  // marker div — a zero-height element is unreliable to observe.
  const addButtonRef = useRef<HTMLButtonElement>(null);
  const { addItem, openDrawer } = useCart();

  const selected = variants.find((v) => v.id === selectedId) ?? variants[0];
  if (!selected) return null;

  const pricingRows = bulkPricingRows(bulkTiers);
  const strengthText = selected.strength ? formatStrength(selected.strength) : selected.format;
  const coasForStrength = coas.filter((coa) => coa.strength === selected.strength);
  const latestForStrength = latestCoaForStrength(coas, selected.strength);

  const handleAdd = () => {
    addItem(selected.id, quantity);
    openDrawer();
  };

  return (
    <div>
      <span className={styles.priceNow}>{formatMoney(selected.price_cents)}</span>

      {variants.length > 1 && (
        <>
          <span className={styles.fieldLabel}>Strength</span>
          <div className={styles.variantOptions}>
            {variants.map((variant) => (
              <button
                key={variant.id}
                type="button"
                className={`${styles.variantOption} ${variant.id === selectedId ? styles.variantOptionSelected : ""}`}
                onClick={() => setSelectedId(variant.id)}
              >
                {variant.strength ? formatStrength(variant.strength) : variant.format}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Quantity + Add to Cart sit directly under the price so they are on
          the first screen without scrolling (David, 9/5); the tier table,
          spec list and format notice follow. */}
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


      {pricingRows.length > 1 && (
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
                        aria-label={`${rangeLabel(row)} vials`}
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
          <dt>{supply ? "Size" : "Strength"}</dt>
          <dd>{strengthText}</dd>
        </div>
        <div className={styles.specRow}>
          <dt>Contents</dt>
          <dd>{productName}</dd>
        </div>
        <div className={styles.specRow}>
          <dt>Form</dt>
          <dd>{supply ? "Sealed vial" : "Lyophilized powder, sealed vial"}</dd>
        </div>
        <div className={styles.specRow}>
          <dt>Certificates</dt>
          <dd>
            {coas.length > 0 ? (
              <LabReportLink className={styles.coaLink}>
                {latestForStrength
                  ? `${coasForStrength.length} on file for ${strengthText} · latest ${formatCoaDate(latestForStrength.issued_on)} · ${distinctLabs(coasForStrength).join(", ")}`
                  : `${coas.length} on file (other strengths)`}
              </LabReportLink>
            ) : (
              "Available on request"
            )}
            {sdsUrl && (
              <>
                {" · "}
                <a className={styles.coaLink} href={sdsUrl} target="_blank" rel="noopener noreferrer">
                  Safety Data Sheet
                </a>
              </>
            )}
          </dd>
        </div>
      </dl>

      {!supply && <FormatNotice form={selected.form} />}

      <StickyBuyBar
        watchRef={addButtonRef}
        priceCents={selected.price_cents}
        quantity={quantity}
        onQuantityChange={setQuantity}
        onAdd={handleAdd}
      />
    </div>
  );
}
