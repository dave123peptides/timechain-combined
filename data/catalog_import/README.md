# data/catalog_import

Drop TimeChain's own wholesale/retail price sheet (the `.xlsx` source of
truth for `products`/`product_variants` pricing and names) here, then run
the import. This directory is mounted read-write into the `api` container
at `/data/catalog_import` (see `docker-compose.yml`), so any file placed
here is immediately visible inside the container without a rebuild.

**Never commit the spreadsheet or generated reports** — both are
gitignored (`data/catalog_import/*.xlsx`, `data/catalog_import/report_*.json`).
The spreadsheet is proprietary pricing data; the reports are just a local
working artifact for reviewing pending supplier matches.

See `services/api/app/catalog_import/` for the import implementation:

- Parses every sheet of the price sheet (header row auto-detected per
  sheet, same "known candidate names, fail loudly" style as
  `worker/supplier_sync/mapping.py`).
- Get-or-creates `Product`/`ProductVariant` rows, keyed by a deterministic
  slug/SKU so re-running the import is idempotent. New rows are always
  `is_active=False` / `is_sellable=False` — a human opts a product in
  later; re-importing never touches that flag once set.
- Scores each row against the current `supplier_products` catalog and
  classifies it `EXACT` / `LIKELY` / `AMBIGUOUS` / `NO_MATCH`. Only
  `EXACT` — a high-confidence, unambiguous top match — auto-creates a
  `supplier_product_mappings` row. Everything else is written to a JSON
  report here for manual review, never auto-linked.

Run it with:

```sh
docker compose exec api pip install '.[import]'   # openpyxl, one-time per container
docker compose exec api python -m app.catalog_import.run "/data/catalog_import/<your-file>.xlsx"
```

Prints a summary (rows retrieved, products/variants created vs. existing,
EXACT mappings created, and pending counts by status) and writes the full
pending-match candidate list to `report_<timestamp>.json` in this
directory.
