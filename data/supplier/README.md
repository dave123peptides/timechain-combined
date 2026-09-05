# data/supplier

The manual JSON-file import approach (fetching sandbox pages by hand and
dropping them here) has been superseded — supplier products are now
fetched live from the AllianceTek Sandbox Products API.

See `services/worker/worker/supplier_sync/` for the sync implementation:

- Paginates automatically using the API's own `result.pages` / `result.total`
  (never hard-codes a page or product count).
- Validates the final fetched count against `result.total` before writing
  anything to the database.
- Upserts into `supplier_products` only — never touches `products`,
  `product_variants`, or `supplier_product_mappings`.

Run it manually with:

```sh
docker compose exec worker python -m worker.supplier_sync
```

Requires `SUPPLIER_API_PRODUCTS_URL`, `SUPPLIER_API_EMAIL`, and
`SUPPLIER_API_TOKEN` to be set (see `.env.example` at the repo root).
Never put real values for these in source control.

This directory is kept as a place for non-secret local fixtures if a
future need for them comes up (e.g. a recorded sample response for
tests) — nothing currently lives here.
