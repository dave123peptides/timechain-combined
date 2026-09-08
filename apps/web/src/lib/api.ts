// Server components run this fetch from inside the `web` container, where
// "localhost" resolves to the container itself, not the api service — they
// need the Docker network service name (API_INTERNAL_BASE_URL). Client
// components run in the browser on the host, which needs the published
// port (NEXT_PUBLIC_API_BASE_URL). Only NEXT_PUBLIC_* vars are ever
// inlined into the browser bundle, so this branch is resolved per-context
// automatically — server code never ships the internal URL to the client.
function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.API_INTERNAL_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

export type Variant = {
  id: string;
  name: string;
  format: string;
  // Raw form key ("pen" for everything sellable on this site; the API
  // still knows "lyophilized"/"preconstituted"/etc) — `format` above is
  // the display label. Components that branch on physical form key off
  // this (FormatNotice).
  form: string | null;
  strength: string | null;
  price_cents: number;
};

// One third-party Certificate of Analysis: one lab report for one lot of
// one strength. pdf_url is the lab's own hosted copy and verify_url its
// verification page for verify_code — the customer checks the document
// with the lab, not with us. `tests` is the assay panel printed on the
// certificate (labels only, never results: the number stays inside the
// certificate, in its own context — see ProofSection).
export type ProductCoa = {
  verify_code: string;
  // Same shape as Variant.strength ("10", "10/10/50", "10mL") so the Lab
  // report cards line up with the strength picker; formatStrength()
  // renders both.
  strength: string | null;
  lot: string;
  // ISO date — the day the lab certified the results.
  issued_on: string;
  lab: string;
  tests: string[];
  pdf_url: string;
  verify_url: string | null;
};

export type ProductSummary = {
  slug: string;
  name: string;
  description: string | null;
  category: string | null;
  images: string[];
  starting_price_cents: number;
  variants: Variant[];
  // Certificate rollup, on the summary so ProductCard's badge and /coa
  // don't need a detail fetch per product. 0 / null is the honest "none
  // held" state, which the UI renders as "available on request" — never
  // as a substitute claim.
  coa_count: number;
  coa_latest_issued_on: string | null;
  // Safety Data Sheet URL; null renders as "available on request".
  sds_url: string | null;
};

export type ProductFaqEntry = {
  q: string;
  a: string;
};

export type ProductContent = {
  overview: string | null;
  key_points: string[];
  research_areas: string[];
  pairs_with: string[];
  faq: ProductFaqEntry[];
};

export type ProductDetail = {
  slug: string;
  name: string;
  description: string | null;
  category: string | null;
  images: string[];
  variants: Variant[];
  content: ProductContent;
  // Every published certificate, already in Lab-report order (strength
  // ascending, newest first). Empty is the honest "none held" state.
  coas: ProductCoa[];
  // See ProductSummary.
  sds_url: string | null;
};

// /coa's unit: one sellable product and all of its published
// certificates. Products holding none are absent — the page lists those
// as "on request" from listProducts instead.
export type CoaIndexEntry = {
  slug: string;
  name: string;
  coas: ProductCoa[];
};

export type ShippingAddress = {
  line1: string;
  line2?: string | null;
  city: string;
  region: string;
  postal_code: string;
  country: string;
};

export type OrderItem = {
  name: string;
  quantity: number;
  unit_price_cents: number;
  total_price_cents: number;
};

export type Order = {
  // The only order identifier ever returned by the API — never a
  // sequential database id.
  public_order_number: string;
  access_token: string;
  status: string;
  customer_email: string;
  customer_name: string | null;
  customer_phone: string | null;
  shipping_address: ShippingAddress | null;
  subtotal_cents: number;
  shipping_cents: number;
  tax_cents: number;
  total_cents: number;
  // Checkout discount code snapshot: the normalized code and the cents
  // it took off the subtotal. total_cents already reflects it.
  discount_code: string | null;
  discount_cents: number;
  items: OrderItem[];
  created_at: string;
  // Provider of the newest payment row — which instructions the order
  // page shows. Null only for a hand-edited order with no payment row.
  payment_method: string | null;
  // Only ever populated on the checkout-create response (see
  // PaymentInstructions) — null on order-status fetches.
  payment?: PaymentInstructions | null;
};

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(response.status, payload?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export { ApiError };

// Sort keys the API recognises. Anything else falls back to name order
// server-side rather than erroring, so this type is a convenience for
// callers, not a validation boundary.
export type ProductSort = "name" | "price_asc" | "price_desc";

export type ProductFilters = {
  category?: string;
  format?: string;
  // Case-insensitive substring match over name/slug/description.
  q?: string;
  sort?: ProductSort;
};

export function listProducts(filters?: ProductFilters): Promise<ProductSummary[]> {
  const params = new URLSearchParams();
  if (filters?.category) params.set("category", filters.category);
  if (filters?.format) params.set("format", filters.format);
  // Trimmed and length-capped to match the API's own max_length=100 —
  // a whitespace-only term is no filter at all, not a search for "".
  const term = filters?.q?.trim();
  if (term) params.set("q", term.slice(0, 100));
  if (filters?.sort) params.set("sort", filters.sort);
  const query = params.toString();
  return apiFetch<ProductSummary[]>(`/shop/products${query ? `?${query}` : ""}`);
}

// Public read-only pages must NEVER render a crash page just because the
// API is unreachable (e.g. the web service deployed before the api service
// has a public home). They present an empty catalog instead — the same
// "nothing available right now" state as a genuinely empty shop. Catalog
// pages use this; checkout/quote keep the strict listProducts so money
// paths still fail loud.
export async function listProductsOrEmpty(
  filters?: ProductFilters
): Promise<ProductSummary[]> {
  try {
    return await listProducts(filters);
  } catch {
    return [];
  }
}

// True when the API could not be reached at all (fetch rejects with a
// TypeError on connection failure) — as opposed to an HTTP error like 404,
// which callers may need to distinguish (e.g. product not found).
export function isUnreachable(err: unknown): boolean {
  return err instanceof TypeError || (err instanceof ApiError && err.status >= 500);
}

export type ShopFilterOptions = {
  categories: string[];
  formats: string[];
};

export function getFilterOptions(): Promise<ShopFilterOptions> {
  return apiFetch<ShopFilterOptions>("/shop/filter-options");
}

export type BulkDiscountTier = {
  min_quantity: number;
  percent_off: number;
};

// Display-only — the real per-order price is always confirmed server-side
// by quoteCheckout/createOrder (see app.constants.bulk_discounts, the
// single source of truth this list mirrors).
export function getBulkDiscountTiers(): Promise<BulkDiscountTier[]> {
  return apiFetch<BulkDiscountTier[]>("/shop/bulk-discount-tiers");
}

export function getProduct(slug: string): Promise<ProductDetail> {
  return apiFetch<ProductDetail>(`/shop/products/${encodeURIComponent(slug)}`);
}

export function listCoas(): Promise<CoaIndexEntry[]> {
  return apiFetch<CoaIndexEntry[]>("/shop/coas");
}

// Same degrade-to-empty stance as listProductsOrEmpty: /coa is a public
// read-only page and must never crash because the API is unreachable.
export async function listCoasOrEmpty(): Promise<CoaIndexEntry[]> {
  try {
    return await listCoas();
  } catch {
    return [];
  }
}

export type ConsentInput = {
  age_confirmed: boolean;
  ruo_acknowledged: boolean;
  terms_accepted: boolean;
};

export type CartItemInput = { variant_id: string; quantity: number };

// "venmo" and "zelle" are the launch methods (David, 9/4): the customer
// sends the transfer themselves with the order number as the memo and
// an admin confirms it. "crypto" (Speed's hosted Bitcoin checkout) and
// "ach" stay in the type for existing orders; the checkout lists them as
// coming soon. Details and how-to copy: lib/paymentMethods.ts.
export type PaymentMethod = "venmo" | "zelle" | "crypto" | "ach";

// Present only on the POST /checkout/create response — the provider's
// instructions for how to pay (a Speed hosted checkout URL for crypto).
// GET /shop/orders/{token} never returns it.
export type PaymentInstructions = {
  provider: string;
  summary: string;
  details: {
    provider_payment_id?: string;
    checkout_url?: string;
    [key: string]: unknown;
  };
};

export function createOrder(payload: {
  email: string;
  customer_name: string;
  customer_phone: string;
  shipping_address: ShippingAddress;
  items: CartItemInput[];
  consent: ConsentInput;
  payment_method: PaymentMethod;
  // The code the quote validated (Quote.discount_code); the server
  // re-validates and re-prices it, and rejects the order if it isn't real.
  discount_code?: string | null;
}): Promise<Order> {
  return apiFetch<Order>("/api/v1/checkout/create", { method: "POST", body: JSON.stringify(payload) });
}

// Retry-payment: mints a fresh Speed checkout session for a still-unpaid
// crypto order. Same response shape as checkout-create.
export function retryPayment(token: string): Promise<Order> {
  return apiFetch<Order>(`/shop/orders/${encodeURIComponent(token)}/retry-payment`, { method: "POST" });
}

export function getOrder(token: string): Promise<Order> {
  return apiFetch<Order>(`/shop/orders/${encodeURIComponent(token)}`);
}

export type ShippingRate = {
  country: string;
  amount_cents: number;
};

export function getShippingRate(): Promise<ShippingRate> {
  return apiFetch<ShippingRate>("/shop/shipping-rate");
}

export type QuoteLine = {
  variant_id: string;
  name: string;
  quantity: number;
  unit_price_cents: number;
  total_price_cents: number;
};

export type Quote = {
  items: QuoteLine[];
  subtotal_cents: number;
  shipping_cents: number;
  tax_cents: number;
  total_cents: number;
  // Set when the request's discount code is valid (normalized code +
  // cents off the subtotal); discount_error, and no discount, when it
  // isn't. The quote itself still succeeds either way.
  discount_code: string | null;
  discount_cents: number;
  discount_error: string | null;
};

// Read-only preview, computed entirely server-side (price, sellability,
// supplier mapping, shipping rate, tax) from just variant_id/quantity —
// the same trust boundary as create_order itself. Used to drive the
// checkout summary display so it can never drift from what the server
// would actually charge.
export function quoteCheckout(payload: {
  items: CartItemInput[];
  country?: string;
  discount_code?: string | null;
}): Promise<Quote> {
  return apiFetch<Quote>("/api/v1/checkout/quote", { method: "POST", body: JSON.stringify(payload) });
}

export function formatMoney(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// Mirrors app.constants.bulk_discounts.discounted_unit_price_cents exactly
// (integer-cents floor, never float) — used only to render the bulk
// pricing table before checkout. The real price for an actual cart/order
// always comes from quoteCheckout/createOrder, never from this.
export function discountedUnitPriceCents(retailPriceCents: number, percentOff: number): number {
  return retailPriceCents - Math.floor((retailPriceCents * percentOff) / 100);
}

// Variant.strength is usually a bare mg number/combo ("1.5", "10",
// "10/10/50") that needs "mg" appended for display, but a value that
// already carries its own unit (e.g. "10mL") must be left alone —
// appending "mg" would read as "10mLmg". Only append when strength is
// purely numeric (decimals allowed) or slash-separated.
export function formatStrength(strength: string): string {
  return /^[\d./]+$/.test(strength) ? `${strength}mg` : strength;
}
