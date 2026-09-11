import type { PaymentMethod } from "@/lib/api";

// Payment methods at checkout. Venmo and Zelle (David, 9/4) are manual
// transfers: the customer sends the money themselves with the public
// order number as the memo, and an admin confirms it arrived. Bitcoin
// (David, 9/10-11) is an OpenNode charge shown on our own order page as
// a QR / open-in-wallet button; OpenNode's webhook confirms the order
// on its own. ACH is listed as coming soon. Every
// string shown at checkout and on the order page for these methods
// comes from here, so the details live in one place.
//
// Zelle details confirmed by David on 2026-09-06 for the vial site and
// applied here on 2026-09-07: the enrolled address is
// support@timechainpeptides.com and the account shows as "Timechain".

export const SUPPORT_EMAIL = "support@timechainpeptides.com";
export const BUSINESS_NAME = "Timechain Ventures LLC";

// Venmo details changed by David on 2026-09-08: payments go to the
// timechainp profile, @timechainp (same as the vial site).
export const VENMO = {
  handle: "@timechainp",
  url: "https://venmo.com/u/timechainp",
};

export const ZELLE = {
  // The address enrolled with Zelle. Kept as its own literal (not SUPPORT_EMAIL)
  // so a support-inbox change can never silently redirect payments.
  recipient: "support@timechainpeptides.com",
  // The name Zelle shows for the recipient (confirmed by David, 2026-09-06).
  accountName: "Timechain",
};

// Manual-transfer methods: the order page shows the send-it-yourself
// instructions (PaymentInstructions) for these while the order is pending.
export type LivePaymentMethod = Extract<PaymentMethod, "venmo" | "zelle" | "bitcoin_opennode">;

export function isLivePaymentMethod(value: string | null | undefined): value is LivePaymentMethod {
  return value === "venmo" || value === "zelle" || value === "bitcoin_opennode";
}

// Hosted-checkout methods: the order page shows the Pay button / payment
// status card for these. "crypto" is the dormant Speed provider, kept so
// any old order still renders.
export type HostedCheckoutMethod = Extract<PaymentMethod, "bitcoin_opennode" | "crypto">;

export function isHostedCheckoutMethod(value: string | null | undefined): value is HostedCheckoutMethod {
  return value === "bitcoin_opennode" || value === "crypto";
}

export type PaymentOption = {
  id: PaymentMethod;
  label: string;
  live: boolean;
  // "transfer": the customer sends money themselves (memo warning shown).
  // "hosted": the customer is taken to a payment page (no memo at all).
  kind: "transfer" | "hosted";
  // One line above the steps, for methods that need a headline.
  intro?: string;
  // The "how it works" panel under the selected option at checkout.
  steps: string[];
};

export const PAYMENT_OPTIONS: PaymentOption[] = [
  {
    id: "venmo",
    label: "Venmo",
    live: true,
    kind: "transfer",
    steps: [
      "Place your order first. Your order number and a link to our Venmo profile appear on the next page.",
      `Send your order total to ${VENMO.handle} on Venmo.`,
      "Enter ONLY your order number in the note. Do not mention peptides or product names.",
      "Your order ships once the payment is received and matched to your order number.",
    ],
  },
  {
    id: "zelle",
    label: "Zelle",
    live: true,
    kind: "transfer",
    steps: [
      "Place your order first. The Zelle details and your order number appear on the next page.",
      // The checkout step names the account only (David, 9/7); the enrolled
      // address is shown on the order page, where the customer actually sends.
      // Quoted so it reads as the name Zelle will display, not a handle
      // (David, 9/8): Zelle has no @usernames, only the registered name.
      `Send your order total via Zelle. The recipient will show up as “${ZELLE.accountName}”.`,
      "Enter ONLY your order number in the memo. Do not mention peptides or product names.",
      "Your order ships once the payment is received and matched to your order number.",
    ],
  },
  {
    id: "bitcoin_opennode",
    label: "Bitcoin (BTC)",
    // Offered only when the build has NEXT_PUBLIC_BITCOIN_CHECKOUT_ENABLED=true
    // (David, 9/10: off on the public site until the OpenNode process is
    // sorted out, on locally). The API has the matching switch,
    // BITCOIN_CHECKOUT_ENABLED, which refuses Bitcoin orders outright.
    live: process.env.NEXT_PUBLIC_BITCOIN_CHECKOUT_ENABLED === "true",
    kind: "hosted",
    intro: "Pay instantly with Bitcoin. Confirmation is automatic.",
    steps: [
      "Place your order. Your Bitcoin payment appears on the next page as a QR code.",
      "Scan it with any Lightning or Bitcoin wallet, or tap Open in wallet. The exact amount is filled in for you.",
      "Your order is confirmed on its own once the payment is received. No memo or note is needed.",
    ],
  },
  { id: "ach", label: "ACH (electronic check)", live: false, kind: "transfer", steps: [] },
];

// Labels for methods no longer offered at checkout but present on old orders.
const LEGACY_LABELS: Record<string, string> = { crypto: "Bitcoin" };

export function paymentOption(id: string | null | undefined): PaymentOption | undefined {
  return PAYMENT_OPTIONS.find((option) => option.id === id);
}

export function paymentMethodLabel(id: string | null | undefined): string | undefined {
  return paymentOption(id)?.label ?? (id ? LEGACY_LABELS[id] : undefined);
}

// Can the customer place an order with this method right now?
export function isSelectablePaymentMethod(value: string | null | undefined): boolean {
  return paymentOption(value)?.live ?? false;
}
