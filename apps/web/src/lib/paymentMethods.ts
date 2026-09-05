import type { PaymentMethod } from "@/lib/api";

// Launch payment methods (David, 9/4): Venmo and Zelle — the customer
// sends the transfer themselves, with the public order number as the
// memo, and an admin confirms it arrived. ACH and Bitcoin are listed as
// coming soon. Every string shown at checkout and on the order page for
// these methods comes from here, so the details live in one place.
//
// TODO(David): confirm the Zelle recipient and the name customers will
// see on the account before this branch ships — both are placeholders.

export const SUPPORT_EMAIL = "support@timechainpeptides.com";
export const BUSINESS_NAME = "Timechain Ventures LLC";

export const VENMO = {
  handle: "@timechain",
  url: "https://www.venmo.com/u/timechain",
};

export const ZELLE = {
  // TODO(David): the email or phone number enrolled with Zelle.
  recipient: "ZELLE-RECIPIENT-TBD",
  // TODO(David): the name Zelle shows for the recipient.
  accountName: BUSINESS_NAME,
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
      `Send your order total via Zelle to ${ZELLE.recipient} — the account will show as “${ZELLE.accountName}”.`,
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
