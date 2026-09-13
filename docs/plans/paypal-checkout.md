# PayPal checkout

Added 2026-09-13 (David's brief, sandbox first). "PayPal" sits next to
Zelle and Bitcoin at checkout on the TCP site. The order is created
pending, the customer is sent to PayPal's approval page and lands back on
their order page, where the payment is captured; PayPal's webhook settles
it as well. A confirmed PayPal order then looks exactly like a confirmed
Zelle or Bitcoin order to staff (same sheet row rewrite, same GHL
"order.paid" push).

## Pieces

- Provider: `services/api/app/payments/paypal.py` (`paypal`), registered in
  `app/payments/registry.py`. Copied from the OpenNode provider's shape:
  blank credentials raise `PayPalNotConfigured` at call time (checkout
  degrades to "order created, no PayPal link yet"), a paid transition only
  ever goes through `app.services.payments.mark_order_paid`.
- Creating the PayPal order: `POST /v2/checkout/orders`, intent CAPTURE,
  `custom_id` = our order number, description `"TCP Order PEN-…"`, brand
  name `PAYPAL_BRAND_NAME` (default `TCP`), `NO_SHIPPING`, `PAY_NOW`,
  `IMMEDIATE_PAYMENT_REQUIRED`, return and cancel URL = the order page.
  **Nothing PayPal sees names a product** (same rule as the OpenNode
  description and the Venmo/Zelle memos). The PayPal order id is stored as
  `Payment.provider_payment_id`; the approval link, expiry (created + 3 h,
  PayPal's default validity) and status as `Payment.provider_data`.
- The customer's return: PayPal sends them to
  `/order/{access_token}?token=<PayPal order id>&PayerID=…`. The order page
  (`PayPalPayment.tsx`) calls `POST /shop/orders/{token}/paypal/capture`
  (`app/api/checkout.py`), which captures (`POST
  /v2/checkout/orders/{id}/capture`), checks the captured amount equals the
  order total (a mismatch is recorded as a `payment_amount_mismatch` order
  event and the order is NOT marked paid), then `mark_order_paid(source=
  "paypal:capture")` and the paid fan-out. 409 = the buyer never approved
  (the page offers Continue to PayPal again); a capture PayPal is still
  completing leaves the payment row `processing`.
- Webhook: `POST /api/v1/webhooks/payments/paypal` (the generic route in
  `app/api/webhooks.py`). Verified with `POST
  /v1/notifications/verify-webhook-signature` (needs `PAYPAL_WEBHOOK_ID`;
  the raw body is spliced into that request byte-for-byte, which PayPal
  requires). Dedupes on `WebhookEvent(source="paypal", external_id=<event
  id "WH-…">)`, which is stable across PayPal's retries and manual resends.
  - `PAYMENT.CAPTURE.COMPLETED`: re-fetch the order (`GET
    /v2/checkout/orders/{id}`), require status COMPLETED and a completed
    capture for exactly the order total in USD, then `mark_order_paid(source=
    "paypal:webhook")`. A lookup failure or a not-COMPLETED answer raises →
    500 → nothing committed → PayPal redelivers.
  - `CHECKOUT.ORDER.APPROVED`: captures server-side (best effort), so a
    customer who closes the tab between approving and landing back still
    ends up paid. Goes one step beyond the brief's "record only" for this
    event; idempotent with the return capture (a second capture answers
    ORDER_ALREADY_CAPTURED, which is treated as success after a re-fetch).
  - `PAYMENT.CAPTURE.DENIED`: payment row `failed`, order stays pending.
    `REFUNDED` / `REVERSED`: recorded on the payment and as an order event,
    no state change. Unknown events: recorded.
  - The return capture and the webhook lock the order row (`SELECT … FOR
    UPDATE`) before capturing, so whichever comes second sees the first
    one's result instead of double-writing history or double-firing the
    fan-out.
- Web: `apps/web/src/lib/paymentMethods.ts` (option + all customer copy),
  `lib/api.ts` (`capturePayPal`), the checkout page (the placement note now
  reads from the selected option; the preselected method is the first live
  one, so a switched-off Venmo is never the silent default), and
  `app/(storefront)/order/[token]/` (`PayPalPayment.tsx`: Continue to
  PayPal, the return capture, "Taking you to PayPal…"; `AutoRefresh` keeps
  polling so the webhook's flip shows up too). Retry-payment mints a fresh
  PayPal order when the stored link is missing or past its three hours.
- GHL/Sheets: no changes needed. `payment_method` rides through the
  existing payloads; `ghl_notify._METHOD_LABELS` gained `paypal → PayPal`.

## Switching it on and off

PayPal is offered only when both switches are true: `PAYPAL_CHECKOUT_ENABLED`
on the API (otherwise `POST /checkout/create` and retry-payment refuse
`paypal` with a 400) and `NEXT_PUBLIC_PAYPAL_CHECKOUT_ENABLED` on the
storefront build (otherwise the option shows as "Coming soon"). The webhook
route and the return capture ignore the switch, so PayPal orders that
already exist still settle. Both are off in production until David says
otherwise; both are on in the local `.env` / `apps/web/.env.local`.

## Environment

API project on Vercel: `tcp-api` (Secret type for the secret). Redeploy
the API after changing any of these.

| Variable | Sandbox (now) | Live (later) |
| --- | --- | --- |
| `PAYPAL_CHECKOUT_ENABLED` | `true` only while testing | `true` |
| `PAYPAL_CLIENT_ID` | sandbox app "TCP Checkout" (David's dashboard, Sandbox tab) | live app |
| `PAYPAL_CLIENT_SECRET` | sandbox secret | live secret |
| `PAYPAL_ENVIRONMENT` | `sandbox` | `live` |
| `PAYPAL_WEBHOOK_ID` | `3G781066FH466404Y` (registered 2026-09-13 via the API for the sandbox app, URL `https://tcp-api-xi.vercel.app/api/v1/webhooks/payments/paypal`, the five event types above) | id of the live webhook (register in the Live dashboard, or `app.payments.paypal.register_webhook(url)` with live credentials) |
| `PAYPAL_BRAND_NAME` | `TCP` | `TCP` |
| `PUBLIC_SITE_URL` | already `https://www.buytcp.com` (builds the return URL) | same |

Web project `tcp-storefront`: `NEXT_PUBLIC_PAYPAL_CHECKOUT_ENABLED=true`
(rebuild required; it is inlined at build time).

The webhook URL is the vercel.app alias because TCP has no custom API
domain; if one is ever added, register a new webhook for it and swap the
id.

**Sandbox on the live domain means sandbox money.** While the production
API carries sandbox credentials with the switch on, anyone who gets past
the site password could place a PayPal order that confirms with fake
funds. Keep the switch off in production except for the sandbox smoke test,
and flip credentials to live before turning it on for real.

## Testing

- Unit: `cd services/api && .venv/bin/pytest -q tests/test_paypal_provider.py tests/test_paypal_webhook_route.py`
  (order payload is peptide-free; forged / unsigned webhook → 400; unknown
  order → acknowledged and ignored; happy path marks paid once and fires the
  fan-out once; double delivery dedupes; amount mismatch blocks; return
  capture + webhook are idempotent in both orders; the checkout gate).
- Forged webhook against a deployment must be rejected:
  `curl -i -X POST -H 'Content-Type: application/json' -d '{"id":"WH-x","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{}}' https://tcp-api-xi.vercel.app/api/v1/webhooks/payments/paypal` → 400 (501 until the code is deployed).
- Sandbox end-to-end: with the sandbox values deployed and both switches
  on, place a small order with PayPal, approve it with a sandbox buyer
  account (developer.paypal.com → Testing Tools → Sandbox Accounts), land
  back on the order page and watch it flip to Order Confirmed; the sheet
  row for that PEN number flips to PAID with no new row; the GHL paid hook
  fires once. The dashboard's Webhook Events page (Sandbox) shows the
  deliveries and lets you resend one; a resend answers `already_processed`.
- PayPal's webhook simulator sends mock events that cannot pass signature
  verification (PayPal's own limitation), so it only ever proves the 400
  path.
- Live: create the Live app, swap the two credentials, set
  `PAYPAL_ENVIRONMENT=live` and the live webhook id, redeploy, one small
  live order, refund it in the PayPal dashboard (the refund webhook is
  recorded on the order's history).

## Known risk

PayPal's acceptable-use policy is hostile to research chemicals and
account holds are common. Every string PayPal sees (brand name, description,
custom_id) is the store name and the order number only; keep it that way.
