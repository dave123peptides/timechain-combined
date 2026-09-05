# services/api/data/coa

`coa_manifest.csv` is the committed record of every third-party Certificate
of Analysis the storefront publishes — one row per certificate, keyed by
the lab's verification code. It is what `product_coas` is loaded from.

**The pen catalog (34 products, 51 pens) has no certificates yet, so this manifest is a header row
only.** Every product page shows the honest "available on request" state
(`LabReport.tsx`) and `/coa` lists every product under "Available on
request". Keep the header row: `sync_coas` (which the Vercel build runs)
accepts a header-only file and fails on an empty one.

## When pen certificates arrive

Drop the PDFs in a folder, one subfolder per compound, named
`{lot}__{supplier_sku}__{verify_code}.pdf`, map each folder to a catalog
slug in `build_coa_manifest._FOLDER_TO_SLUG`, then:

```sh
cd services/api
pip install '.[coa]'                                          # pypdf, once
python -m app.scripts.build_coa_manifest "/path/to/pen COAs"  # rewrites coa_manifest.csv
git diff services/api/data/coa/coa_manifest.csv               # review: new rows only
python -m app.scripts.sync_coas                               # loads into product_coas (local DB)
```

Every fact in a row comes from the certificate's own text; the site links
to the lab's hosted copy and its verification page rather than quoting a
purity figure anywhere (see `ProofSection` and the about page).

`sync_coas` publishes new rows only for clients listed in its
`DEFAULT_PUBLISH_CLIENTS`; other clients load with `is_published = false`
for a person to decide on. Update that tuple for the pen supplier's lab
client name before the first real sync.

## Production

Nothing to run by hand. Every Vercel build of the API applies migrations
and then syncs this manifest — see `scripts/vercel-build.sh`.
