# Local end-to-end test plan

Manual + automated verification of the storefront → order → fulfillment
pipeline against a real local `docker compose` stack. Last executed
2026-08-14 against `main` (commit range up to `e88dcc9`), with results
inline below each step.

**Out of scope for this pass (explicitly deferred):** Whop webhook flow
and duplicate-webhook protection. There is no Whop integration in the
codebase yet (no route, no signature verification, no idempotency
handling) — this section will be written once that work starts.

## 0. Setup

```sh
open -a Docker                 # ensure the daemon is running
cp .env.example .env           # if you don't already have one
docker compose up --build -d
docker compose exec api alembic upgrade head
curl -s http://localhost:8000/healthz   # {"status":"ok"}
```

Notes on `.env` for this pass:
- `SUPPLIER_API_PRODUCTS_URL` + `SUPPLIER_API_EMAIL` + `SUPPLIER_API_TOKEN`
  were already populated with real AllianceTek sandbox values, so catalog
  sync exercises a real endpoint.
- `SUPPLIER_API_ORDERS_URL` (and `_ORDER_STATUS_URL` / `_FULFILLMENTS_URL`
  / `_SHIPMENTS_URL`) were **blank**, so a real order submission can't
  reach AllianceTek yet — see §7. `QUEUE_PROVIDER` was unset, i.e. `local`
  (Postgres-backed queue), not SQS.
- The local DB volume already had data from a prior sync: 70 products,
  164 variants, 214 supplier products, 77 mappings.

## 1. Catalog

Supplier product sync already populated `supplier_products` from the
real AllianceTek sandbox endpoint (`services/worker/worker/supplier_sync`).
Verified via automated suite (`test_supplier_sync.py`, 20 tests covering
pagination, upsert classification, reconciliation) — all passing (§8).

```
GET /shop/products  → 200, 2 sellable products (only variants with an
                       active MAPPED supplier mapping are listed)
GET /shop/products/5-amino-1mq → 200, full variant detail
```

## 2. Mapping

Verified live against `/admin/products`:

| Action | Result |
| --- | --- |
| `GET /admin/products` | row for variant `ae1c329e-5cc8-4033-9f25-066353b95a37` shows `mapping_status="MAPPED"`, `sellable=true`, supplier identity (`supplier_product_id=26395394`, sku `123`, confidence `EXACT`) |
| `POST /admin/products/{id}/disable` | flips `sellable=false`; variant immediately disappears from `GET /shop/products/{slug}` |
| `POST /api/v1/checkout/quote` for the disabled variant | `400 "... is no longer available ..."` |
| `POST /admin/products/{id}/enable` | restores `sellable=true` |

`get_mapping_status` gating (`MAPPED` requires an active mapping row, not
just `is_sellable`) is also covered by `test_admin_products.py` and
`test_storefront.py` in the API suite.

**Gap found:** admin visibility currently covers product/mapping state
only. There is no admin UI or API endpoint listing orders in
`MANUAL_REVIEW` (or any order state) — only `apps/web/src/app/admin/products`
exists. Orders can currently only be inspected via direct DB query (see
§7). Worth a ticket if admin needs to *see* stuck orders without shelling
into Postgres.

## 3. Cart

`GET /shop/products` / `/shop/products/{slug}` return only sellable,
actively-mapped variants with `price_cents` — no supplier data (sku,
wholesale cost, supplier name) leaks into the response, confirmed by
inspecting the JSON shape (`StorefrontVariant` dataclass deliberately
omits those fields).

## 4. Server-side price

`CheckoutItemRequest` only accepts `variant_id` + `quantity` — there is
no price field in the request schema, so there's nothing to tamper with.
Confirmed live:

```
POST /api/v1/checkout/quote {variant_id, quantity: 2}
→ unit_price_cents=4900, total_price_cents=9800 (read from DB, not request)
```

## 5. $40 shipping

```
GET /shop/shipping-rate → {"country":"US","amount_cents":4000}
```

Seeded via migration `5f8e0c58a306` (`shipping.us_flat_rate_cents` =
`{"amount_cents": 4000}`), read fresh from `system_settings` on every
quote/order — not hardcoded in the frontend.

Non-US rejection verified via `POST /checkout/quote {country: "CA"}` →
`400 "We currently ship within the United States only."`
(`GET /shop/shipping-rate` itself has no `country` param — it's a
US-only display preview; the real validation gate is in `build_quote`
and `create_order`, both exercised here.)

## 6. Order creation

```
POST /api/v1/checkout/create
  → 201-shaped 200: public_order_number=TCP-ENJLR9,
    subtotal_cents=4900, shipping_cents=4000, tax_cents=0,
    total_cents=8900, status=PAYMENT_PENDING
```

Confirmed in the DB, same transaction:
- `orders` row with generated `public_order_number` + `access_token`
  (no internal UUID ever exposed to the client)
- `order_items` snapshot (`sku_snapshot`, `display_name_at_purchase`,
  `supplier_*_at_purchase` all frozen at order time)
- `consent_records` row (all three consent flags required — verified via
  `create_order`'s early rejection when any is `false`, covered by
  `test_storefront.py`)
- `payments` row: `provider="not_configured"`, `status="pending"` (no
  real payment processor wired up yet — expected)
- `background_jobs` row: `job_type="submit_supplier_order"`,
  `payload={"order_id": ...}` — enqueued in the same DB transaction as
  the order, so it can never exist without a corresponding order or vice
  versa

Customer order lookup by token also verified:
`GET /shop/orders/{access_token}` → 200 with live status.

## 7. Worker

Worker picked up the `submit_supplier_order` job within ~4 seconds of
enqueue (poll interval 5s). Since `SUPPLIER_API_ORDERS_URL` is blank
(§0), the AllianceTek client raised a config error, which the handler
classifies as **permanent** — no retry, straight to `MANUAL_REVIEW`:

```
orders.status:            MANUAL_REVIEW
supplier_orders.status:   MANUAL_REVIEW
supplier_attempts:        attempt_number=1, status=failed,
                           error_message="SUPPLIER_API_ORDERS_URL is not
                           configured. Set it via environment variable."
order_events:             {"to": "MANUAL_REVIEW", "from": "PAYMENT_PENDING",
                           "reason": "permanent error: SUPPLIER_API_ORDERS_URL
                           is not configured. ..."}
```

This is correct behavior, not a bug — it proves the permanent-error →
`MANUAL_REVIEW` path end-to-end, including the full audit trail
(`supplier_attempts` + `order_events`).

## 8. AllianceTek Sandbox submission

Real order submission requires `SUPPLIER_API_ORDERS_URL` (and ideally
`_ORDER_STATUS_URL`/`_FULFILLMENTS_URL`/`_SHIPMENTS_URL`) to be filled in
`.env` — not available in this pass (§0). Two things stand in for it:

1. `test_alliancetek_sandbox_integration.py` — exercises the exact
   agreed fixture (`supplier productId=25688246`, `sku="234"`,
   `name="Test Sku"`, `orderNumber="TEST-TIMECHAIN-001"`) through the
   real payload builder + client against an `httpx.MockTransport`,
   proving the outgoing payload shape end-to-end without a live network
   call. Passing.
2. §7 above proves the *real* client + real config-validation path is
   wired correctly — it just has no sandbox order endpoint to call yet.

**Follow-up:** once real `SUPPLIER_API_ORDERS_URL` is available, rerun
§6–§7 with it set to get one real sandbox round-trip, then diff the
captured request against the mock fixture.

## 9. Retry logic

Validated via the automated suite rather than waiting through the real
`RETRY_DELAYS_SECONDS` tiers (0 / 30s / 2m / 10m / 30m) — this is more
rigorous than a timed manual test:

- `test_transient_failure_schedules_delayed_retry_not_generic_requeue`
- `test_permanent_failure_on_first_attempt_goes_straight_to_manual_review`
- `test_config_error_also_routes_to_manual_review` (this is the exact
  path exercised live in §7)
- `test_exhausting_all_retry_tiers_routes_to_manual_review`
- `test_eventual_success_after_a_transient_retry`
- `test_submit_supplier_order_retry_reuses_same_supplier_order_number`
  (confirms `orderNumber` is reused verbatim across retries, matching
  AllianceTek's confirmed idempotent-orderNumber behavior)

All passing.

## 10. Admin visibility

Confirmed live (§2): mapping status and sellability changes made via
`/admin/products/*` are immediately reflected in the storefront and in
checkout validation. **Not yet built:** any admin-facing view of order
state (`MANUAL_REVIEW`, `PAYMENT_PENDING`, etc.) — see the gap noted in
§2.

## Automated suite results (2026-08-14)

```
services/api:    58 passed
services/worker: 75 passed
```

```sh
docker compose exec api pip install pytest httpx && docker compose exec api python -m pytest -q
docker compose exec worker pip install pytest httpx && docker compose exec worker python -m pytest -q
```
(dev deps aren't baked into the runtime images — install them ad hoc in
the running container, as above, or run natively per the README's
"Running services individually" section.)

## Known gaps / follow-ups

1. **Whop webhook flow + duplicate-webhook protection** — not
   implemented at all; out of scope until that work starts.
2. **Admin order visibility** — no UI/API surface for `MANUAL_REVIEW` (or
   any) order state; only reachable via direct DB query today.
3. **Real AllianceTek sandbox order submission** — blocked on
   `SUPPLIER_API_ORDERS_URL` (and status/fulfillments/shipments URLs)
   being filled in; currently only the products endpoint is configured.
4. `.env.example` has a duplicated `SQS_QUEUE_URL=` key (harmless, but
   worth a one-line cleanup).
