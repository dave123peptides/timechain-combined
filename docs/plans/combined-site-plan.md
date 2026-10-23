# Combined Pens + Vials Site (timechainpeptides.com) — Implementation Plan

> **For Hermes / head developer:** Execute task-by-task in order. Every file path is relative to the repo root, which is the fork `~/Desktop/timechain-combined` (a copy of the TCP/buytcp.com pens repo, branch `combined-site`). The two ancestor repos are read-only references on the same machine: `~/Desktop/TCP` (pens, buytcp.com) and `~/Desktop/timechain` (vials, fork parent).

**Goal:** One storefront at timechainpeptides.com selling both pre-filled 3 mL auto-injector **pens** and lyophilized **vials**, with a "Pens | Vials" toggle on the shop page filtering one shared catalog.

**Architecture:** This is NOT a merge of two codebases. TCP was forked FROM the vial site on 2026-09-05, so they share the same FastAPI + Next.js monorepo, the same DB schema, and the same supplier-mapping model. The variant model (`ProductVariant.form`: "pen" / "lyophilized" / "preconstituted" / ...) already exists, and the storefront API already supports a `?format=` filter. The work is: (1) remove the pens-only hard guard so vial variants can be sellable, (2) build the Pens|Vials shop filter UI, (3) port the vial catalog seed (`sync_lyo_catalog.py` + its `_LADDER` prices) so both lines are populated, (4) rebrand/domain, (5) deploy to Vercel + Neon as a new project.

**Tech Stack:** Next.js 15.4 (apps/web, App Router), FastAPI + SQLAlchemy (services/api), Python worker (services/worker), Vercel (web + api), Neon Postgres, payments already wired: OpenNode BTC, Whop cards/Apple Pay, Zelle. Tests: pytest (services/api/tests), `npm run lint`/`npm run build` (apps/web).

---

## Decisions and status (David, 2026-10-22, recorded after Task 0)

Task 0 was put to David before any code was written. His answers, and
the one change of direction that reshaped the plan:

1. **Categories: shown on both lines.** The benefit-category pills
   (lib/categories.ts) render for pens and vials alike; the Pens | Vials
   toggle narrows first, the pills narrow within it. The attorney-review
   TODO in that file stands.
2. **One product page per compound.** 29 compounds ship as both a pen
   and a vial and share a row; the PDP has a Format picker (Pen | Vial)
   above Strength. Six are vial-only (aod-9604, bac-water, ghk-cu-kpv,
   ghrp-2, ghrp-6, mt-1), six are pen-only.
3. **New Vercel projects + a fresh Neon database, then move the domain.**
   www.timechainpeptides.com currently serves the vial site (behind its
   password gate); the combined site replaces it. The vial projects stay
   intact as the rollback.
4. **No payments at all.** This is the change the original plan did not
   anticipate: the site is a showcase. Visitors browse, then book a
   meeting from /contact (David will supply the scheduling link:
   `NEXT_PUBLIC_BOOKING_URL`; email until then). Task 5 (mixed-cart
   checkout) is therefore moot. Instead: `ORDERING_ENABLED` on the API
   (default off, checkout writes answer 503, catalog unaffected) and
   `NEXT_PUBLIC_ORDERING_ENABLED` on the web (default off: no cart
   drawer, no Add to Cart, /cart and /checkout redirect to /contact).
   The checkout code stays in the tree behind those two switches.
5. **Supplier mappings: placeholder pattern**, as both sites launched.

Done in this repo (branch `combined-site`, commits 4b2e8c3..6e83466):
Tasks 1 (local DB `tcp_combined`), 2, 3 (as `seed_lyo_catalog`, a seed
rather than a port of `sync_lyo_catalog`, since this DB starts empty),
4, 6, and the inquiry-mode work above. Task 7 (deploy) is a runbook for
David: `docs/plans/combined-site-launch.md`. Task 8: TCP and the vial
repo were not touched.

---

## Current state (what exists, verified 2026-10-22)

### Repo layout (identical in all three repos)
```
apps/web                 Next.js storefront (this is what Vercel serves)
services/api             FastAPI app (app/api/{shop,checkout,admin,webhooks,health}.py)
services/worker          supplier catalog sync (does NOT run for TCP — FULFILLMENT_MODE=manual)
app constants            services/api/app/constants/forms.py  ← FORM_LABEL dict
```

### The two catalogs today
- **Pens (TCP/buytcp.com):** seeded by `services/api/app/scripts/seed_pen_catalog.py` (346 lines). Products keyed by slug (`glp-1s`, `bpc-157`, …), variants have `form="pen"`, sellable via placeholder SupplierProducts under supplier_key `"umsrx"` (pens supplier). Benefit categories rendered on the storefront from `apps/web/src/lib/categories.ts` (David's 2026-09-05 decision — pens site only; the vial site deliberately never rendered categories for compliance).
- **Vials (timechain/):** seeded by `services/api/app/scripts/sync_lyo_catalog.py`. `_LADDER` dict at ~line 36 = slug → {size_key: retail_price_cents} (Final Pricing 9.1.26 sheet). Variants `form="lyophilized"`, supplier_key `"nxgen"`. **This file does not exist in TCP/the fork — it must be ported.** Also port `activate_pending_lyo_variants.py` and `apply_lyo_vial_photos.py` if wanted (check `~/Desktop/timechain/services/api/app/scripts/`).
- Supplier model supports both lines already: `SupplierProduct.supplier_key` docstring in `services/api/app/models/catalog.py:234-240` explicitly says the middleware serves two disjoint catalogs ("umsrx" = pens & pre-constituted, "nxgen" = lyophilized vials) and every lookup must filter on supplier_key.

### The one hard blocker
`services/api/app/models/catalog.py:163-205` — `ProductVariant._validate_is_sellable` **raises unless `self.form == "pen"`** (line 182). The vial site has the mirror-image rule. On the combined site this guard must allow both `"pen"` and `"lyophilized"` (decide below: keep `preconstituted`/`rx_vial`/`vial`/`other` blocked — vial site policy 2026-08-22 was "lyophilized vials only", pens site policy was "pens only"; combined = the union of the two).

### API already supports format filtering
- `services/api/app/api/shop.py:274-291` — `GET /shop/products?format=<form>` (alias of `ProductVariant.form`), plus `q`, `sort`, `category`.
- `services/api/app/api/shop.py:294-303` — `GET /shop/filter-options` returns `{categories, formats}` from live sellable data.
- `services/api/app/services/storefront.py:415` `list_sellable_products(db, category=..., form=..., q=..., sort=...)`; `_format_label()` at :208 maps via `app/constants/forms.py` `FORM_LABEL`.
- Frontend fetch layer: `apps/web/src/lib/api.ts:208-217` — `listProducts({q, sort, format})` already sets a `format` query param; `ProductSummary` type carries both `format` (label) and `form` (raw key) per variant.

### Frontend today (pens-only copy)
- `apps/web/src/app/(storefront)/shop/page.tsx` — banner says "Pre-filled 3 mL auto-injector pens. Ready to use — no reconstitution." (line 49); comment at lines 20-25 explains there is deliberately no format filter because every variant is a pen.
- `apps/web/src/components/catalog/CatalogGrid.tsx:44-46` — standing line "Every product ships as a 3 mL auto-injector pen."
- `apps/web/src/components/FormatNotice.tsx` — **already has per-form notices for pen AND lyophilized** (reconstitution copy included). No change needed here; it keys off raw `form`.
- `apps/web/src/components/CategoryPills.tsx` — benefit-category pills. NOTE compliance TODO in `lib/categories.ts` header: benefit-named categories were a pens-site decision; vial-site rules (docs/plans/claude-answers-glp-decision.md in the vial repo) banned them as intended-use claims. **Decision needed (Task 0) — see Open Questions.**
- `apps/web/src/lib/supplies.ts` exists only in the vial repo — BAC water is a "reconstitution supply" rendered differently on the PDP. Port if vials are included (they are — reconstitution water is a natural attach).

### Tests that pin the pens-only behavior (must be updated, not deleted)
- `services/api/tests/test_sellable_guard.py` — asserts non-pen forms are blocked (`_make_variant(..., form="pen")` default at :51).
- `services/api/tests/test_seed_pen_catalog.py`
- `services/api/tests/test_storefront.py` — fixtures use `form="vial"` (:88) and assert `_format_label` mapping (:138-140).

---

## Task 0: Decisions to confirm with David BEFORE coding (blocking)

1. **Categories on the combined site.** Pens site shows benefit categories ("Weight Loss", "Sexual Health"…). Vial site banned them (intended-use claims — `lib/categories.ts` header TODO(attorney-review), vial repo `docs/plans/claude-answers-glp-decision.md`). Combined site: keep pills on the Pens tab and hide on Vials tab (recommended — preserves each line's compliance posture), or unify either way. Attorney review flagged either way.
2. **Which vial products.** The vial `_LADDER` (~36 slugs incl. `bac-water`) vs pens (~34 slugs) overlap heavily by slug (same compounds, different form). Both lines will sell e.g. `bpc-157` — as two variants under ONE product page (pen 10mg pen + lyophilized 10mg vial on the same PDP) or as separate product rows? **Recommended: one product row per slug; the strength picker on the PDP already lists variants — add the format label (already in `VariantResponse.format`) to the picker so a shopper sees "10mg — Pen $X / 10mg — Lyophilized $Y".** This is the smallest change and the toggle just filters grid rows by whether any sellable variant matches the chosen form.
3. **Domain/DNS:** timechainpeptides.com — registrar access, DNS control, and whether it's already pointed anywhere. Vercel project + Neon branch to create (names below).
4. **Payments:** confirm the combined site should carry OpenNode BTC + Whop cards/Apple Pay + Zelle from day one (TCP's live config), PayPal stays off (aborted 9/14).
5. **Supplier mappings for vials:** the vial site's lyo variants may have real verified nxgen mappings in ITS database. Combined site DB starts fresh (see Task 1) — either re-run the same placeholder pattern `seed_pen_catalog.py` uses (`_PLACEHOLDER_ID_BASE = 900_000_000`, MANUAL/MAPPED rows) for vials, or export mapping rows from the vial Neon DB. **Recommended: placeholder pattern first, map real SKUs via /admin/products later — that's exactly how both sites went live.**

## Task 1: Set up the combined repo + fresh database

**Objective:** Turn the fork into an independent project with its own DB so nothing touches buytcp.com or the vial site.

**Steps:**
1. Repo is already forked at `~/Desktop/timechain-combined`, branch `combined-site`, origin set to `https://github.com/dave123peptides/timechain-combined.git` (create empty repo on GitHub first, then `git push -u origin combined-site`).
2. Create a new Neon project/branch, e.g. `timechain-combined`. **Do not reuse the `timechain-prod` (command center), tcp-api, or vial-site databases.**
3. Update `docker-compose.yml` + `services/api/.env` / `.env.local` for local dev: `POSTGRES_DB=tcp-combined` (or similar), new `DATABASE_URL`.
4. Run migrations from scratch against the new DB: from `services/api`, `alembic upgrade head` (check `services/api/alembic/` for the revision list; both sites share history).
5. Commit: `chore: point combined-site fork at its own database`.

**Verify:** `alembic current` shows head; `GET /health` (app/api/health.py) returns ok locally.

## Task 2: Allow both forms in the sellable guard (TDD)

**Files:**
- Modify: `services/api/app/models/catalog.py:163-205` (`_validate_is_sellable`)
- Test: `services/api/tests/test_sellable_guard.py`

**Step 1 — write failing tests** (append to `test_sellable_guard.py`, reuse its fixtures):
```python
def test_pen_variant_can_be_sellable(session):            # already passes — guard
def test_lyophilized_variant_can_be_sellable(session):   # fails today (line 182 raises)
def test_preconstituted_variant_still_blocked(session):   # passes today, must keep passing
def test_rx_vial_and_plain_vial_still_blocked(session):  # passes today, must keep passing
```
**Step 2 — run:** `cd services/api && python -m pytest tests/test_sellable_guard.py -v` → expect the lyophilized test to FAIL with the ValueError from catalog.py:184.

**Step 3 — implement.** Replace the form check at catalog.py:182:
```python
_SELLABLE_FORMS = ("pen", "lyophilized")  # module-level, next to FORM_LABEL usage docs

if self.form not in _SELLABLE_FORMS:
    raise ValueError(
        f"Cannot set is_sellable=True on variant {self.sku!r}: "
        f"form {self.form!r} is not sold on this site."
    )
```
Update the validator docstring to say "combined site sells pens and lyophilized vials" and reference both prior policies by date (pens 2026-09-05, vials 2026-08-22).
**Step 4:** pytest green; then run the FULL api suite (`python -m pytest`) — `test_seed_pen_catalog.py`, `test_storefront.py`, `test_mapping_status.py` all touch this guard; fix any that assumed pens-only.
**Step 5 — commit:** `feat: allow pen and lyophilized variants to be sellable (combined site)`

## Task 3: Port the vial catalog seed

**Files:**
- Create: `services/api/app/scripts/sync_lyo_catalog.py` (copy from `~/Desktop/timechain/services/api/app/scripts/sync_lyo_catalog.py`, 150 lines) and adapt:
  - its docstring's "lyophilized only" policy note → combined-site note
  - it currently HIDES every non-lyophilized variant (line ~126: `if variant.form != "lyophilized"` → hide). **On the combined site that would hide the pens.** Change the hide rule to only hide forms outside `_SELLABLE_FORMS` from Task 2 — import the constant, don't restate it.
- Port `app/constants/product_categories.py` differences if the vial repo's taxonomy is newer (diff both, keep union).
- Optional ports: `activate_pending_lyo_variants.py`, `apply_lyo_vial_photos.py`, `sync_product_content.py`, and `services/api/app/catalog_import/` + `data/` (COA manifest) — diff against fork, port what's vial-specific.
- Port `apps/web/src/lib/supplies.ts` (BAC-water supply rendering) + its usages (`grep -rl supplies apps/web/src` in the vial repo: Footer.tsx among others). Copy the vial-site product images for lyo products from `~/Desktop/timechain/apps/web/public/products/` into the fork's `apps/web/public/products/` (don't overwrite pen files; filenames differ — verify per file).
- Also seed pens: `python -m app.scripts.seed_pen_catalog` runs unchanged (it only upserts its own slugs/SKUs).

**Order of a full seed on the fresh DB:** `seed_pen_catalog` → `sync_lyo_catalog` → (COAs: `build_coa_manifest` + `sync_coas` if porting certificates).

**Verify:**
```bash
python - <<'EOF'
from app.db.session import SessionLocal
from sqlalchemy import text
s = SessionLocal()
print(s.execute(text("select form, count(*) from product_variants where is_sellable group by form")).fetchall())
EOF
# expect [('pen', N), ('lyophilized', M)]
curl 'localhost:8100/shop/products?format=lyophilized' | jq length   # vials only
curl 'localhost:8100/shop/filter-options' | jq                       # formats: ["Pen","Lyophilized"]
```
**Commit:** `feat: port lyophilized vial catalog from the vial site`

## Task 4: Pens | Vials toggle on the shop (frontend)

**Files:**
- Modify: `apps/web/src/app/(storefront)/shop/page.tsx` (parse `?form=` param; banner copy becomes form-aware: pens copy when form=pen, vials copy when form=lyophilized, combined default copy)
- Create: `apps/web/src/components/catalog/FormPills.tsx` (+ `.module.css`) — modeled directly on `CategoryPills.tsx` (same router-push pattern, `data-hermes` nothing; plain links: `/shop?form=pen`, `/shop?form=lyophilized`, `/shop`). Label from `FORM_LABEL`-equivalent — add a client-safe map in `lib/api.ts` or reuse the `format` display string the API returns. Options should ideally derive from `GET /shop/filter-options` (already in `lib/api.ts:252`) so pills disappear if a line has no stock.
- Modify: `apps/web/src/components/catalog/CatalogGrid.tsx` — accept the form filter; replace the hardcoded "Every product ships as a 3 mL auto-injector pen." note (:44-46) with a dynamic one; render `FormPills` above `CategoryPills`.
- Modify: `apps/web/src/lib/api.ts` — `listProductsOrEmpty`/`listProducts` already accept `format` (:208-217); just pass it through from the shop page. **A product row matches a form if ANY of its variants has that form** — do this client-side (`products.filter(p => p.variants.some(v => v.form === form))`) since the API's `?format=` filters at variant level and returns the product with only matching variants (check `storefront.py:454-455` behavior and match the UI to it; if the API returns products whose variant list is pre-filtered, the grid needs no extra filter).
- Modify homepage `apps/web/src/app/(storefront)/page.tsx` — it renders `CatalogGrid` too; give it the same toggle or a neutral "shop pens / shop vials" link pair.
- PDP `apps/web/src/app/(storefront)/shop/[slug]/page.tsx` — strength picker shows each variant's `format` label (already in the API response, `VariantResponse.format`, shop.py:22) so pen vs vial prices are distinguishable on one product page. `FormatNotice.tsx` already handles per-form copy — no change.
- Update `lib/categories.ts` header comment per Task 0 decision #1 (if pills stay pens-only, gate `CategoryPills` render on the active form).

**Verify:**
```bash
cd apps/web && npm run lint && npm run build
npm run dev   # manual: /shop shows both, Pens pill filters to pens, Vials to vials,
              # PDP for a dual product shows "10mg — Pen $X" and "10mg — Vial $Y",
              # cart + checkout work with a mixed pen+vial cart
```
**Commit:** `feat: pens|vials format toggle on shop and PDP format labels`

## Task 5: Cart & checkout audit for mixed carts

**Files to read (not necessarily change):** `apps/web/src/lib/cart-context.tsx`, `useResolvedCart.ts` (vial-repo file — port if missing in fork), `services/api/app/api/checkout.py`, `app/services/storefront.py` `create_order`.

**Objective:** A cart containing a pen and a vial must price, discount (bulk tiers — `app/constants/bulk_discounts.py`), ship, and push to ShipStation correctly. Order push reads supplier SKU/name from `SupplierProductMapping` (supplier_key denormalized at catalog.py:298) — verify a mixed order routes pen lines to `umsrx` token and vial lines to `nxgen` token. Add one pytest: mixed-cart order creation → both order items carry correct supplier_key.

**Commit:** `test: mixed pen+vial cart prices and routes to both suppliers`

## Task 6: Branding + domain (timechainpeptides.com)

**Files:**
- `apps/web/src/app/layout.tsx` + `(storefront)/layout.tsx` — site name/meta ("Timechain Peptides" replaces TCP pens branding), favicon/icons (copy `icon.svg`/`apple-icon.png` from the vial repo `apps/web/src/app/` — already there, verified).
- `apps/web/src/components/{Header,Footer}.tsx` — nav/footer copy; Footer references supplies (Task 3).
- Legal pages: `(storefront)/privacy`, `(storefront)/terms` — update entity/payment copy per combined line (review before launch; compliance skill exists — peptide-regulatory-compliance).
- `apps/web/.env*` — `NEXT_PUBLIC_API_BASE_URL` → new Vercel api service URL; keep payment flags per Task 0 #4 (`NEXT_PUBLIC_BITCOIN_CHECKOUT_ENABLED`, `NEXT_PUBLIC_WHOP_CHECKOUT_ENABLED`; leave PayPal false).
- Age gate `(storefront)/age-gate` unchanged.

**Commit:** `chore: rebrand combined site for timechainpeptides.com`

## Task 7: Deploy

1. GitHub: push `combined-site`; repo `dave123peptides/timechain-combined`.
2. Vercel: new project from the repo — the root `vercel.json` already defines services `web` (apps/web), `api` (services/api, entrypoint `app.main:app`), `worker`; same shape as the two live sites. Set env vars: Neon `DATABASE_URL` (combined), payment keys (OpenNode, Whop, Zelle display, GHL webhook), `CHECKOUT_ENABLED`, `FULFILLMENT_MODE=manual` (same as TCP).
3. Neon: `timechain-combined` DB, run `alembic upgrade head` + both seed scripts against production BEFORE flipping DNS.
4. DNS: point timechainpeptides.com A/CNAME at Vercel.
5. Pre-launch safety (David's standing rule): flip Speed key to IP-allowlist, register webhooks (OpenNode + Whop + GHL), void-test orders first, sandbox-test payments, then live.
6. GHL: BTC email branch webhook (`e8761c08` pattern, From @lc, `{{order_url}}`) — add the new site's checkout URL to the GHL flow, or clone the flow for the new domain.

## Task 8: Regression sweep (both existing sites must be untouched)

- `cd ~/Desktop/TCP && git status` → only the pre-existing Whop modifications (whop.py, test_whop_provider.py — uncommitted on main before this project; do not touch).
- Confirm the vial repo `~/Desktop/timechain` untouched.
- buytcp.com and the vial site still resolve and checkout.

---

## Verification checklist (definition of done)

- [ ] `GET /shop/products` returns products with BOTH `form: "pen"` and `form: "lyophilized"` variants
- [ ] `?format=pen` → pens only; `?format=lyophilized` → vials only; `/shop/filter-options` lists both
- [ ] Shop page Pens | Vials toggle filters the grid; count text is accurate
- [ ] PDP of a dual product (e.g. bpc-157) shows both formats with distinct prices and the right FormatNotice copy
- [ ] Mixed cart → checkout → order created; ShipStation payload has correct supplier lines
- [ ] `python -m pytest` (services/api) fully green; `npm run lint && npm run build` green
- [ ] timechainpeptides.com serves the site; test order (sandbox payment) completes; live payments re-enabled after
- [ ] buytcp.com and vial site unaffected

## Risks / open questions

- **Compliance (biggest):** benefit categories on vials = intended-use claim exposure (attorney TODO already in `lib/categories.ts`). GLP code-name slugs rule (`lib/compliance.ts`) must keep applying to both lines.
- **Dual-product PDP UX:** one row per compound with mixed pen/vial variants is the recommended shape but needs David's sign-off (Task 0 #2) — it changes how shoppers compare.
- **Placeholder supplier mappings self-expire** if a catalog sync ever runs (`seed_pen_catalog.py` docstring) — combined site must keep `FULFILLMENT_MODE=manual`, same as TCP.
- **Prices:** vial `_LADDER` is the 9.1.26 sheet; confirm still current before seeding prod.
- **SEO/canonical:** two existing live domains + one new combined site selling overlapping catalogs — decide whether buytcp.com and the vial site stay up, redirect, or wind down; until decided, all three run independently (separate DBs, separate Vercel projects).
