# services/api/data/coa

`coa_manifest.csv` is the committed record of every third-party Certificate
of Analysis the storefront publishes — one row per certificate, keyed by
the lab's verification code. It is what `product_coas` is loaded from.

The certificate PDFs themselves are **not** in the repo (about 400 MB, and
the lab already hosts every one of them publicly). They live in David's
"Timechain COAs" folder, one subfolder per compound, named
`{lot}__{supplier_sku}__{verify_code}.pdf`. The storefront links to the
lab's hosted copy (`pdf_url`) and to its verification page (`verify_url`),
so a customer checks a certificate with the lab, not with us.

## Updating after new certificates arrive

```sh
cd services/api
pip install '.[coa]'                                              # pypdf, once
python -m app.scripts.build_coa_manifest "/path/to/Timechain COAs"   # rewrites this coa_manifest.csv
git diff services/api/data/coa/coa_manifest.csv                                # review: new rows only, nothing rewritten
python -m app.scripts.sync_coas                                   # loads into product_coas (local DB)
```

Run `sync_coas` against production from a dev box the same way migrations
are run (`DATABASE_URL=... python -m app.scripts.sync_coas`).

Every fact in a row comes from the certificate's own text — strength from
the lab's "SAMPLE SIZE", `issued_on` from its "PUBLISHED DATE", `tests`
from the assay rows on the report. The filename supplies only the lot and
verification code, and the builder fails the run if either is missing from
the PDF. A new compound folder must be mapped to a catalog slug in
`build_coa_manifest._FOLDER_TO_SLUG` before it will load.

`client` is the company the lab issued the certificate to. `sync_coas`
publishes new rows only for our supplier (NxGen Bio Med) by default; rows
for any other client load with `is_published = false` for a person to
decide on. See the docstrings of both scripts for the rules.

Never store a purity figure here or anywhere else — the certificate
carries the number in its own context, and the site links to it rather
than quoting it (see `ProofSection` and the about page).

## Production

Nothing to run by hand. Every Vercel build of the API (`vercel --prod`
from `services/api`) applies migrations and then syncs this manifest into
the production database — see `scripts/vercel-build.sh`. Commit the
manifest, deploy, done.
