"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { createOrder, formatMoney, type PaymentMethod } from "@/lib/api";
import { useCart } from "@/lib/cart-context";
import { PAYMENT_OPTIONS, isSelectablePaymentMethod, paymentOption } from "@/lib/paymentMethods";
import { useResolvedCart } from "@/lib/useResolvedCart";
import ProductImagePlaceholder from "@/components/ProductImagePlaceholder";
import SectionIcon from "@/components/SectionIcon";
import CheckoutSteps, { type StepIndex } from "./CheckoutSteps";
import styles from "./page.module.css";

// Core-reference checkout (David, 9/4): three steps — Information,
// Shipping, Payment — in bordered panels on the left, the Order Summary
// on the right, consents and "Place your order" under the summary on
// the last step. One page, one form's worth of state: the steps only
// decide which panel is showing, so nothing is lost moving back.
//
// Totals are always the server's quote (useResolvedCart → /checkout/
// quote), never computed here — the same trust boundary as the charge
// itself in create_order. That includes the discount code (David, 9/6):
// the typed code goes to the server on the quote, which answers with
// the normalized code and cents off (or an error to show inline), and
// only a code the quote accepted is sent with the order.
export default function CheckoutPage() {
  const router = useRouter();
  const { clear } = useCart();
  const [codeInput, setCodeInput] = useState("");
  const [appliedCode, setAppliedCode] = useState<string | null>(null);
  const codeFieldId = useId();
  const { hydrated, loading, lines, quote, quoteError, hasUnavailable } = useResolvedCart(true, appliedCode);
  const available = lines.filter((line) => line.variant);

  const [step, setStep] = useState<StepIndex>(0);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [region, setRegion] = useState("");
  const [postalCode, setPostalCode] = useState("");
  // Preselect the first method that can actually be chosen, so a method
  // switched off (Venmo, 9/11) is never the silent default.
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>(
    () => PAYMENT_OPTIONS.find((option) => option.live)?.id ?? "zelle",
  );
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [ruoAcknowledged, setRuoAcknowledged] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const consentComplete = ageConfirmed && ruoAcknowledged && termsAccepted;
  const canPlace =
    consentComplete && quote !== null && !hasUnavailable && isSelectablePaymentMethod(paymentMethod) && !submitting;
  const selectedOption = paymentOption(paymentMethod);

  const placeOrder = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const order = await createOrder({
        email,
        customer_name: fullName.trim(),
        customer_phone: phone.trim(),
        shipping_address: {
          line1,
          line2: line2 || null,
          city,
          region,
          postal_code: postalCode,
          // United States only at launch — see the fixed field on step 1.
          country: "US",
        },
        items: available.map((line) => ({ variant_id: line.variantId, quantity: line.quantity })),
        consent: { age_confirmed: ageConfirmed, ruo_acknowledged: ruoAcknowledged, terms_accepted: termsAccepted },
        payment_method: paymentMethod,
        discount_code: quote?.discount_code ?? null,
      });
      clear();
      // The order page shows the Bitcoin payment itself (QR + open in
      // wallet) — no redirect to a hosted checkout (David, 9/11). PayPal
      // orders get their Continue to PayPal button there too.
      router.push(`/order/${order.access_token}`);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  };

  if (!hydrated || loading) {
    return (
      <main className="container">
        <div className={styles.head}>
          <h1>Checkout</h1>
        </div>
      </main>
    );
  }

  if (available.length === 0) {
    return (
      <main className="container">
        <div className={styles.head}>
          <h1>Checkout</h1>
        </div>
        <div className={styles.empty}>
          <p>Your cart is empty.</p>
          <br />
          <Link href="/shop" className="button buttonPill buttonAccentOutline">
            Browse the Collection
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <div className={styles.head}>
        <h1 className={styles.title}>Checkout</h1>
        <CheckoutSteps current={step} />
      </div>

      <div className={styles.layout}>
        <div>
          {step === 0 && (
            <form
              className={styles.panel}
              onSubmit={(event) => {
                event.preventDefault();
                setStep(1);
              }}
            >
              <span className={styles.legend}>Contact &amp; shipping details</span>
              <div className={styles.fields}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>
                    Full name <span className={styles.req}>*</span>
                  </span>
                  <input
                    required
                    autoComplete="name"
                    className={styles.input}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                  <span className={styles.fieldHint}>The name the parcel is addressed to.</span>
                </label>
                <div className={styles.row2}>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>
                      Email <span className={styles.req}>*</span>
                    </span>
                    <input
                      type="email"
                      required
                      autoComplete="email"
                      className={styles.input}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                    <span className={styles.fieldHint}>Your order confirmation and status link go here.</span>
                  </label>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>
                      Phone <span className={styles.req}>*</span>
                    </span>
                    <input
                      type="tel"
                      required
                      minLength={7}
                      autoComplete="tel"
                      className={styles.input}
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                    />
                    <span className={styles.fieldHint}>Only used if there&apos;s a question about your order.</span>
                  </label>
                </div>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>
                    Street address <span className={styles.req}>*</span>
                  </span>
                  <input
                    required
                    autoComplete="address-line1"
                    className={styles.input}
                    value={line1}
                    onChange={(e) => setLine1(e.target.value)}
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Apartment, suite, etc. (optional)</span>
                  <input autoComplete="address-line2" className={styles.input} value={line2} onChange={(e) => setLine2(e.target.value)} />
                </label>
                <div className={styles.row2}>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>
                      City <span className={styles.req}>*</span>
                    </span>
                    <input required autoComplete="address-level2" className={styles.input} value={city} onChange={(e) => setCity(e.target.value)} />
                  </label>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>
                      State <span className={styles.req}>*</span>
                    </span>
                    <input required autoComplete="address-level1" className={styles.input} value={region} onChange={(e) => setRegion(e.target.value)} />
                  </label>
                </div>
                <div className={styles.row2}>
                  <label className={styles.field}>
                    <span className={styles.fieldLabel}>
                      ZIP code <span className={styles.req}>*</span>
                    </span>
                    <input required autoComplete="postal-code" className={styles.input} value={postalCode} onChange={(e) => setPostalCode(e.target.value)} />
                  </label>
                  <div className={styles.field}>
                    <span className={styles.fieldLabel}>Country / Region</span>
                    <div className={styles.fixedField}>United States (US)</div>
                    <span className={styles.fieldHint}>We currently ship within the United States only.</span>
                  </div>
                </div>
              </div>
              <div className={styles.panelActions}>
                <button type="submit" className={`button buttonPill buttonAccent ${styles.wide}`}>
                  Continue to Shipping
                </button>
              </div>
            </form>
          )}

          {step === 1 && (
            <form
              className={styles.panel}
              onSubmit={(event) => {
                event.preventDefault();
                setStep(2);
              }}
            >
              <span className={styles.legend}>Shipping details</span>
              <div className={styles.fields}>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>Ship to</span>
                  <div className={styles.fixedField}>
                    <strong>{fullName}</strong>
                    <br />
                    {line1}
                    {line2 ? `, ${line2}` : ""}
                    <br />
                    {city}, {region} {postalCode}
                    <br />
                    United States
                  </div>
                </div>
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>Shipping method</span>
                  <label className={`${styles.choice} ${styles.choiceActive}`}>
                    <input type="radio" name="shipping" checked readOnly />
                    <span className={styles.choiceLabel}>
                      <span>US shipping · flat rate</span>
                      <span className={styles.choicePrice}>{quote ? formatMoney(quote.shipping_cents) : "—"}</span>
                    </span>
                  </label>
                  <span className={styles.fieldHint}>One rate for every US order. Carrier and transit details are in your confirmation email.</span>
                </div>
              </div>
              <div className={styles.panelActions}>
                <button type="submit" className={`button buttonPill buttonAccent ${styles.wide}`}>
                  Continue to Payment
                </button>
                <button type="button" className={`button buttonPill buttonAccentOutline ${styles.wide}`} onClick={() => setStep(0)}>
                  <SectionIcon name="chevronLeft" size={16} /> Return to Details
                </button>
              </div>
            </form>
          )}

          {step === 2 && (
            <div className={styles.paymentList} role="radiogroup" aria-label="Payment method">
              {PAYMENT_OPTIONS.map((option) => {
                const active = paymentMethod === option.id;
                return (
                  <div key={option.id} className={`${styles.paymentOption} ${active && option.live ? styles.paymentOptionOpen : ""}`}>
                    <label className={`${styles.paymentHead} ${option.live ? "" : styles.paymentHeadOff}`}>
                      <input
                        type="radio"
                        name="paymentMethod"
                        value={option.id}
                        checked={active}
                        disabled={!option.live}
                        onChange={() => setPaymentMethod(option.id)}
                      />
                      <span className={styles.paymentName}>{option.label}</span>
                      {!option.live && <span className={styles.soon}>Coming soon</span>}
                    </label>
                    {active && option.live && (
                      <div className={styles.paymentBody}>
                        {option.intro && <p className={styles.howToIntro}>{option.intro}</p>}
                        <ol className={styles.howTo}>
                          {option.steps.map((text) => (
                            <li key={text}>{text}</li>
                          ))}
                        </ol>
                        {option.kind === "transfer" && (
                          <p className={styles.howToWarn}>Do not leave notes or mention peptides in the memo.</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <aside className={styles.side}>
          <div className={styles.panel}>
            <span className={styles.legend}>Order Summary</span>
            <ul className={styles.items}>
              {available.map((line) => (
                <li key={line.variantId} className={styles.item}>
                  <span className={styles.qtyBadge}>{line.quantity}</span>
                  <span className={styles.thumb}>
                    {line.image ? (
                      // eslint-disable-next-line @next/next/no-img-element -- product images are arbitrary URLs from Product.images
                      <img src={line.image} alt="" />
                    ) : (
                      <ProductImagePlaceholder name={line.variant?.name ?? "?"} />
                    )}
                  </span>
                  <span className={styles.itemName}>{line.variant?.name}</span>
                  <span className={styles.itemPrice}>
                    {line.quoteLine ? formatMoney(line.quoteLine.total_price_cents) : "—"}
                  </span>
                </li>
              ))}
            </ul>
            <div className={styles.discount}>
              {quote?.discount_code ? (
                <div className={styles.discountApplied}>
                  <span className={styles.discountAppliedLabel}>
                    <SectionIcon name="check" size={16} /> Code <strong>{quote.discount_code}</strong> applied
                  </span>
                  <button
                    type="button"
                    className={styles.discountRemove}
                    onClick={() => {
                      setAppliedCode(null);
                      setCodeInput("");
                    }}
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <form
                  className={styles.discountForm}
                  onSubmit={(event) => {
                    event.preventDefault();
                    setAppliedCode(codeInput.trim() || null);
                  }}
                >
                  <label className={styles.fieldLabel} htmlFor={codeFieldId}>
                    Discount code
                  </label>
                  <div className={styles.discountRow}>
                    <input
                      id={codeFieldId}
                      className={`${styles.input} ${styles.discountInput}`}
                      value={codeInput}
                      onChange={(e) => setCodeInput(e.target.value)}
                      autoComplete="off"
                      autoCapitalize="characters"
                      spellCheck={false}
                      placeholder="Enter code"
                    />
                    <button type="submit" className="button buttonPill buttonAccentOutline" disabled={!codeInput.trim()}>
                      Apply
                    </button>
                  </div>
                  {appliedCode && quote?.discount_error && <p className={styles.error}>{quote.discount_error}</p>}
                </form>
              )}
            </div>
            <div className={styles.totals}>
              <div className={styles.totalRow}>
                <span>Subtotal</span>
                <span className={styles.accent}>{quote ? formatMoney(quote.subtotal_cents) : "—"}</span>
              </div>
              {quote && quote.discount_cents > 0 && (
                <div className={styles.totalRow}>
                  <span>Discount ({quote.discount_code})</span>
                  <span className={styles.accent}>&minus;{formatMoney(quote.discount_cents)}</span>
                </div>
              )}
              <div className={styles.totalRow}>
                <span>Shipping</span>
                <span>{quote ? formatMoney(quote.shipping_cents) : step === 0 ? "Next step" : "—"}</span>
              </div>
              {quote && quote.tax_cents > 0 && (
                <div className={styles.totalRow}>
                  <span>Tax</span>
                  <span>{formatMoney(quote.tax_cents)}</span>
                </div>
              )}
              <div className={styles.grand}>
                <span>Total</span>
                <span className={styles.accent}>{quote ? `${formatMoney(quote.total_cents)} USD` : "—"}</span>
              </div>
            </div>
            {quoteError && <p className={styles.error}>{quoteError}</p>}
            {hasUnavailable && <p className={styles.error}>Remove unavailable items from your cart to continue.</p>}
          </div>

          {step === 2 && (
            <div className={styles.consents}>
              <label className={styles.consentRow}>
                <input type="checkbox" checked={ageConfirmed} onChange={(e) => setAgeConfirmed(e.target.checked)} />
                <span>I confirm that I am at least 21 years old.</span>
              </label>
              <label className={styles.consentRow}>
                <input type="checkbox" checked={ruoAcknowledged} onChange={(e) => setRuoAcknowledged(e.target.checked)} />
                <span>
                  I understand that everything on this site is for laboratory research use only and not for human or
                  veterinary use, per the{" "}
                  <Link href="/research-use-only" target="_blank">
                    Research Use Only
                  </Link>{" "}
                  terms.
                </span>
              </label>
              <label className={styles.consentRow}>
                <input type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} />
                <span>
                  I agree to the{" "}
                  <Link href="/terms" target="_blank">
                    Terms of Service
                  </Link>{" "}
                  and{" "}
                  <Link href="/privacy" target="_blank">
                    Privacy Policy
                  </Link>
                  .
                </span>
              </label>
              <button type="button" className={`button buttonPill buttonAccent ${styles.wide}`} disabled={!canPlace} onClick={placeOrder}>
                {submitting ? "Placing your order…" : "Place your order"}
              </button>
              <button type="button" className={`button buttonPill buttonAccentOutline ${styles.wide}`} onClick={() => setStep(1)}>
                <SectionIcon name="chevronLeft" size={16} /> Return to Shipping
              </button>
              {error && <p className={styles.error}>{error}</p>}
              <p className={styles.note}>
                {selectedOption?.kind === "hosted"
                  ? `Placing your order reserves it as pending. You finish paying with ${selectedOption.label} on the next page; your order ships once the payment is confirmed.`
                  : `Placing your order reserves it as pending. Payment instructions for ${selectedOption?.label ?? "your payment method"} appear on the next page; your order ships once the transfer is received.`}
              </p>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
