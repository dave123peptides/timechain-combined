import type { PaymentMethod } from "@/lib/api";

// Launch payment methods (David, 9/4): Venmo and Zelle — the customer
// sends the transfer themselves, with the public order number as the
// memo, and an admin confirms it arrived. ACH and Bitcoin are listed as
// coming soon. Every string shown at checkout and on the order page for
// these methods comes from here, so the details live in one place.
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

export type LivePaymentMethod = Extract<PaymentMethod, "venmo" | "zelle">;

export function isLivePaymentMethod(value: string | null | undefined): value is LivePaymentMethod {
  return value === "venmo" || value === "zelle";
}

export type PaymentOption = {
  id: PaymentMethod;
  label: string;
  live: boolean;
  // The "how it works" panel under the selected option at checkout.
  steps: string[];
};

export const PAYMENT_OPTIONS: PaymentOption[] = [
  {
    id: "venmo",
    label: "Venmo",
    live: true,
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
  { id: "ach", label: "ACH (electronic check)", live: false, steps: [] },
  { id: "crypto", label: "Bitcoin", live: false, steps: [] },
];

export function paymentOption(id: string | null | undefined): PaymentOption | undefined {
  return PAYMENT_OPTIONS.find((option) => option.id === id);
}
