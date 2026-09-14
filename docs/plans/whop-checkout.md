# Card / Apple Pay via Whop

Added 2026-09-14 (David's brief), ported the same day from the vial site
(`~/Desktop/timechain`, commits 24fdf0c / 599962a / 5878ae2). "Credit /
Debit Card or Apple Pay" sits first in the checkout list, above Zelle,
PayPal and Bitcoin. The order is created pending, the order page shows a
Pay Now button that links to Whop's hosted checkout (the merchant shown
there is "Timechain Consulting"), Whop sends the customer back to the order
page, and Whop's `payment.succeeded` webhook marks the order paid with no
admin step. A confirmed card order then looks exactly like a confirmed
Zelle, PayPal or Bitcoin order to staff (same sheet row rewrite, same GHL
`order.paid` push).

## Pieces

- Provider: `services/api/app/payments/whop.py` (`whop`), registered in
  `app/payments/registry.py` next to `bitcoin_opennode` and `paypal`. Same
  shape as the OpenNode provider: blank key → `WhopNotConfigured` at call
  time, the checkout degrades (order created, no Pay Now link, the order
  page offers Try again).
- Checkout creation: `POST https://api.whop.com/api/v1/checkout_configurations`
  with `Authorization: Bearer <key>` and an `Api-Version-Date` pin
  (`WHOP_API_VERSION_DATE`, default `2026-09-11-1`). Body: an inline
  one-time plan (`title: "Order PEN-…"`, `initial_price` in dollars,
  `currency: usd`), `metadata: {order_number}`, and `redirect_url` = the
  customer's order page (`PUBLIC_SITE_URL/order/<token>`). The response's
  `id` (`ch_…`) is stored as `Payment.provider_payment_id` and its
  `purchase_url` as `provider_data.checkout_url` (the Pay Now link). Only
  the order number and amount are ever sent — no names, emails or products.
- Webhook: `POST /api/v1/webhooks/payments/whop` (the existing generic
  route in `app/api/webhooks.py`). Standard Webhooks verification: the
  `webhook-id` / `webhook-timestamp` / `webhook-signature` headers, HMAC-SHA256
  over `id.timestamp.body` keyed with the raw `ws_…` secret (never stripped
  or decoded), a 5-minute timestamp window, any of several `v1,` signatures
  accepted. Dedupes on `WebhookEvent(source="whop", external_id = the msg_ id)`,
  which Whop reuses on retries.
- On `payment.succeeded`: the Payment row is found by the `pay_` or `ch_` id
  (fallback: the order number in `metadata`), the payment is re-fetched with
  `GET /payments/{id}` and must read as paid (`status` paid/succeeded or
  `substatus` succeeded) or the route answers 500 with nothing committed so
  Whop retries. The amount (`total`, then `usd_total`, then `subtotal`; number,
  string or Money object) must be USD and at least the order total:
  - short, unreadable or wrong currency → the row becomes `underpaid`, a
    `payment_amount_mismatch` order event records why, the order stays
    pending for staff (admin Mark paid resolves it);
  - more than the total (Whop-side tax) → paid, with the same event recorded.
  Then `mark_order_paid` (order PAID, `provider_payment_id` becomes the `pay_`
  id, card brand / last4 / paid_at merged into `provider_data`) and the
  fan-out in `app/services/order_paid.py`.
- Other events: `payment.pending` / `payment.authorized` set the row
  `processing` (the order page says "being confirmed" and stops offering Pay
  Now); `payment.failed` / `payment.canceled` set it `failed` (the order page
  offers Try again); refunds, disputes and anything new are recorded on the
  payment only. A `succeeded` row is never downgraded.
- Gate: `WHOP_CHECKOUT_ENABLED` in `app/api/checkout.py`
  (`_method_switches()` / `_require_method_enabled`, shared with the Bitcoin
  and PayPal switches) refuses `POST /checkout/create` and retry-payment for
  `whop` with 400 "Card checkout is not available right now…" while off.
- Web: `apps/web/src/lib/paymentMethods.ts` (option + copy + the `WHOP`
  merchant constant), the checkout page (preselects the first live method;
  method-neutral placement note), and `app/(storefront)/order/[token]/`:
  `WhopPayment.tsx` renders the Pay Now link / processing / underpaid /
  Try again states inside the order page's card, with `AutoRefresh`
  re-rendering until the webhook lands. `PayButton` ("Try again") re-mints
  a checkout through the existing retry-payment endpoint. No server actions:
  every call is one of the existing POST route handlers.
- GHL/Sheets: no changes needed. The payload carries `payment_method: "whop"`
  and `payment_method_label: "Card / Apple Pay"`.

## Switching it on and off

Card checkout is offered only when both switches are true:
`WHOP_CHECKOUT_ENABLED` on the API (otherwise `POST /checkout/create` and
retry-payment refuse `whop` with a 400) and `NEXT_PUBLIC_WHOP_CHECKOUT_ENABLED`
on the storefront build (otherwise the option shows as "Coming soon" at the
top of the list and Zelle is preselected). The webhook route ignores the
switch, so checkouts that already exist still settle. As of 2026-09-14 both
are off in production. Locally, set `WHOP_CHECKOUT_ENABLED=true` in the
API's `.env` and `NEXT_PUBLIC_WHOP_CHECKOUT_ENABLED=true` in
`apps/web/.env.local` (the PayPal switches are on there already); with no
`WHOP_API_KEY` the option shows and an order is created, but the order page
offers Try again instead of Pay Now. Turning it on in production means
setting both vars in Vercel and redeploying API then web (the web flag is
inlined at build time).

## Whop dashboard setup (David)

1. Developer → API keys: an account API key. Goes in `WHOP_API_KEY`.
2. Developer → Webhooks → add endpoint
   `https://tcp-api-xi.vercel.app/api/v1/webhooks/payments/whop`,
   subscribed to `payment.succeeded` (required) plus `payment.failed`,
   `payment.pending` and `refund.created` (recommended; they only update the
   payment row and history). If the dashboard offers an API version pin for
   the webhook, pin it to `2026-09-11-1` to match `WHOP_API_VERSION_DATE`.
   Copy the endpoint's signing secret (`ws_…`) verbatim into
   `WHOP_WEBHOOK_SECRET`.
3. Statement descriptor / company name: "Timechain Consulting" (the copy at
   checkout says so).
4. Turn OFF any Whop-side tax collection and do not create Whop promo codes
   for these plans: our total already includes shipping and tax, and a
   different amount shows up as a `payment_amount_mismatch` event (tax → paid
   but recorded; a discount → blocked as underpaid).

Both storefronts can share one Whop account: register one webhook endpoint
per API (this one and the vial site's), each with its own signing secret.
An event for the other site's order matches nothing here and is
acknowledged 200 with a warning log line.

## Environment

API project on Vercel: `tcp-api`. Redeploy after changing any of these.

| Variable | Sandbox (testing) | Live |
| --- | --- | --- |
| `WHOP_CHECKOUT_ENABLED` | `true` | `true` when launching, else unset/`false` |
| `WHOP_API_KEY` | sandbox key | live account key |
| `WHOP_WEBHOOK_SECRET` | the sandbox endpoint's `ws_…` | the live endpoint's `ws_…` |
| `WHOP_ENVIRONMENT` | `sandbox` (cards only, no Apple Pay) | `live` (default) |
| `WHOP_API_VERSION_DATE` | `2026-09-11-1` | `2026-09-11-1` (blank = the key's own pin) |
| `WHOP_ACCOUNT_ID` | blank | blank unless Whop refuses checkout creation without a `biz_…` id |
| `PUBLIC_SITE_URL` | `http://localhost:3100` (http allowed) | already `https://www.buytcp.com` (builds `redirect_url`) |
| `GHL_ORDER_PAID_WEBHOOK_URL` | — | inbound webhook of the GHL "payment confirmed" workflow; blank = no paid push |

Storefront project (`tcp-storefront`): `NEXT_PUBLIC_WHOP_CHECKOUT_ENABLED=true`
to show the option (rebuild required; inlined at build time).

The webhook URL to register is the API's own host,
`https://tcp-api-xi.vercel.app/api/v1/webhooks/payments/whop`; there is no
callback URL setting on our side. It is the vercel.app alias because TCP has
no custom API domain; if one is ever added, register a new endpoint for it
and swap the secret.

## Testing

- Unit: `cd services/api && .venv/bin/python -m pytest -q tests/test_whop_provider.py tests/test_whop_webhook_route.py tests/test_whop_checkout_flag.py`
  (signature and money parsing, verification incl. replay window and
  multiple signatures, every event path incl. under/over-payment, checkout
  creation request shape and compliance, the route's idempotency and 500
  semantics, both switches).
- Forged webhook must be rejected (works against local uvicorn or the live URL):
  ```sh
  curl -i -X POST https://tcp-api-xi.vercel.app/api/v1/webhooks/payments/whop \
    -H 'content-type: application/json' -H 'webhook-id: msg_forged' \
    -H "webhook-timestamp: $(date +%s)" -H 'webhook-signature: v1,ZGVhZGJlZWY=' \
    -d '{"id":"msg_forged","type":"payment.succeeded","data":{"id":"pay_x","total":1,"metadata":{"order_number":"PEN-NOPE"}}}'
  ```
  → `400 {"detail":"Webhook verification failed: webhook-signature does not match."}`.
  Missing headers → 400; a stale `webhook-timestamp` → 400.
- Signed webhook with production code (the secret must match the running API):
  ```sh
  BODY='{"id":"msg_local_1","type":"payment.succeeded","data":{"id":"pay_local_1","checkout_configuration_id":"ch_local_1","status":"paid","substatus":"succeeded","total":129.0,"currency":"usd","metadata":{"order_number":"PEN-XXXXXX"}}}'
  TS=$(date +%s)
  SIG=$(cd services/api && printf '%s' "$BODY" | WHOP_WEBHOOK_SECRET=ws_localtest .venv/bin/python -c 'import os,sys; from app.payments.whop import compute_signature; print(compute_signature(os.environ["WHOP_WEBHOOK_SECRET"], "msg_local_1", sys.argv[1], sys.stdin.buffer.read()))' "$TS")
  curl -i -X POST http://localhost:8100/api/v1/webhooks/payments/whop \
    -H 'content-type: application/json' -H 'webhook-id: msg_local_1' \
    -H "webhook-timestamp: $TS" -H "webhook-signature: $SIG" --data-binary "$BODY"
  ```
  With no `WHOP_API_KEY`: 500 (the paid re-check raises, nothing committed).
  Unknown order number: `200 {"status":"processed"}` plus a warning log line.
  The same `msg_` id again: `{"status":"already_processed"}`.
- Sandbox end to end (optional): `WHOP_ENVIRONMENT=sandbox` + a sandbox key +
  a tunnel to local uvicorn (port 8100) registered as the sandbox webhook;
  place an order with the card option, Pay Now → Whop's page → test card →
  sent back → the page flips to "Order Confirmed" within ~8 s; the payments
  row is `succeeded` with a `pay_…` id and `card_last4`; no
  `payment_amount_mismatch` event; the sheet row is rewritten; GHL paid
  push fires once. The sandbox has no Apple Pay.
- First live test (David, the launch path): set the live key and secret,
  switch both flags on, redeploy API then web, run the forged-webhook curl
  against the live URL (400), then place the cheapest real pen order and pay
  with Apple Pay; confirm the order page flips, the sheet row flips to PAID
  with no new row, GHL fires once, and refund the payment in Whop
  (`refund.created` is recorded, the order stays PAID — cancel it from
  /admin/orders if needed).

## Known risks

- The Whop-side amount can differ from ours only through Whop features we
  do not use (tax collection, promo codes). Keep both off; the mismatch
  event makes it visible if it happens.
- If Whop rejects `Api-Version-Date: 2026-09-11-1` (400 "unknown version"),
  set `WHOP_API_VERSION_DATE` blank to fall back to the key's own pin. If
  checkout creation demands an account id, set `WHOP_ACCOUNT_ID`. Both
  failure modes degrade to "no Pay Now link" (the order still exists), never
  to a broken checkout.
- While `WHOP_API_KEY` is blank but the webhook endpoint is live, every
  `payment.succeeded` answers 500 until the key is set — Whop retries for
  about three days. That is the intended fail-closed behaviour, not a bug.
- The customer can land back on the order page a second or two before the
  webhook does; the page keeps Pay Now plus an "Already paid? this page
  updates on its own" hint until `AutoRefresh` picks up the change.
  Subscribing to `payment.pending` hides Pay Now sooner.
- Other products sold on the same Whop account (including the vial site's
  orders) produce unrelated `payment.succeeded` events; they match no order
  here and are acknowledged 200 with a warning log line.
- Every string Whop sees is the order number and the amount; the Whop
  company name is what the customer's statement shows.

## GHL

The pens site's own new-order workflow (`GHL_ORDER_WEBHOOK_URL`, distinct
from the vial site's) receives `payment_method: "whop"`,
`payment_method_label: "Card / Apple Pay"` and `pay_url` (the order page,
where the Pay Now button lives) with `event: "order.created"`. As with
Bitcoin and PayPal, the workflow needs its own If/Else branch on
`payment_method` equals `whop` (subject "Your TCP order is reserved — pay by
card", body: order number + total + "click Pay Now on your order page:
{{pay_url}}" + "your order confirms on its own once the payment goes
through") or the Venmo email goes out. The paid workflow on
`GHL_ORDER_PAID_WEBHOOK_URL` receives `event: "order.paid"` for every
method, unchanged.
