# Pens fork (TCP) — decisions and setup

Forked from `timechain-storefront` at `8d087b5` on 2026-09-05 into
`~/Desktop/TCP` as an independent repo. The vial site was not modified.

## Decisions (David, 2026-09-05)

| Topic | Decision |
|---|---|
| Brand | Same TimeChain Peptides brand: wordmark, support email, Venmo `@timechain`, Zelle placeholder, Timechain Ventures LLC. |
| Product line | Pre-filled 3 mL auto-injector pens only. No vials, no BAC water, no COAs yet. `ProductVariant._validate_is_sellable` now rejects every form except `pen` (the vial site's rule inverted). |
| Catalog source | `services/api/app/scripts/seed_pen_catalog.py` — the 2026-09-05 pen price sheet: 34 products, 51 pens, suggested-retail prices. Idempotent; replaces the four vial-era sync scripts and the xlsx importer. |
| GLP naming | Code-name slugs kept; display names carry the real name in parentheses ("GLP-3R (Retatrutide)"). `TODO(attorney-review)`. See `claude-answers-glp-decision.md` addendum. |
| Size labels | Strength only ("1.5mg"). "Month N" from the sheet is fulfillment-only (placeholder supplier row name → the sheet's `items` column). |
| Orders | Same Google Sheet and `Orders` tab as the vial site; pen orders are numbered `PEN-XXXXXX`. |
| Images | David's renders (`assets/pen-images/`, as delivered) → `apps/web/public/products/pens/<slug>-<size>.<ext>`; hero cut-outs via `apps/web/scripts/pen-cutouts.py`. |
| Deployment | Not done in this pass. No `.vercel/` links exist in this repo; `vercel link` to NEW projects before any deploy. |

## Side-by-side with the vial site

| | Vial site | Pens site (TCP) |
|---|---|---|
| Postgres DB | `timechain` | `tcp` (+ `tcp_test`) |
| API / web ports | 8000 / 3000 | 8100 / 3100 |
| Gate cookies | `tc_access`, `tc_age_ack` | `tcp_access`, `tcp_age_ack` (cookies ignore ports) |
| localStorage | `timechain_cart`, `timechain_admin_*` | `tcp_cart`, `tcp_admin_*` |
| Compose project | `timechain` | `tcp` (ports 5433/8100/3100) |
| Order prefix | `TCP-` | `PEN-` |

## Render mapping (source file → product)

GLP-1S: `GLP-1S-15/35/55/75-blue-pen.png`, `GLP1-S-10.jpg` · GLP-2T: `GLP2-T-10…60.jpg` ·
GLP-3R: `GLP3-R-8/16-/24/40.jpg`, `Photo Mar 25 2026, 11 51 09 AM (2).jpg` (32 mg), `GLP-3R-48-purple-pen.png` ·
Tesamorelin-30 · Red-Pen-Sermorelin-10mg · Tesa-Ipa-12-3 · Red-Pen-GLOW-10-10-50mg · CJC-IPA (10/10) ·
BPC-157-20 (stands in for the 10 mg pen too) · TB-500 · NAD+500 · PT-141-10 · IGF-LR3-1 · MOTS-C-10/Mots-C--20/MOTS-C-40 ·
Cagrilinitide-10 · GHK-Cu-50 · TA-1-10 · Epithalon-10-red-pen.png (label reads 60 mg) · Kisspeptin-5 · KPV-10 · LL37-10 ·
Selank-20 · Semax-20 · SS-31-50 · DSIP-5 · Dihexa-10 · Gluthathione-600 · 5Amino-1-50.

Second delivery (`assets/pen-images/updated-2026-09-05/`, 2170×725 with extra white space, cropped and
downscaled to the 830×195 framing by the one-off Pillow step recorded in the git history): Ipamorelin 10,
KLOW 10/10/10/50, CJC-1295 no DAC 10, Wolverine 10/10, HCG 3, Hexarelin 5. Every product now has a render.
**Label text to fix on those renders (David/designer):** the KLOW pen lists KPV, LL-37, Oxytocin and White
Adipose Tissue Extract (sheet says KPV/BPC-157/TB-500/GHK-Cu); the Wolverine pen lists CJC-1295 and
Ipamorelin (should be BPC-157/TB-500); Ipamorelin, Hexarelin and HCG carry a stray "(No DAC)". Replacing a
file under `apps/web/public/products/pens/` with the same name is all a corrected render needs.

Renders in `assets/pen-images/` for products not on the sheet (unused): AOD-9604, B3 1000, FOX-04,
MT-I, MT-II, NAD 1000/1600, GLP-1S 15 mg, GLP1-S 1 mg, Tesamorelin 10, Ipamorelin 30, BPC-100, Tesa/Ipa 40/10,
and the six large "GLP-xx PEN Nmg.JPEG" photo sets.

## Open items for David

- Confirm the pen line's compounding/testing facts (`TODO(David)` in `HomeHero.tsx`, `TrustStrip.tsx`, `shop/page.tsx`).
- Zelle recipient/account name are still placeholders (`lib/paymentMethods.ts`), same as the vial site.
- Attorney review of the parenthetical GLP names.
- Corrected label text on the KLOW, Wolverine, Ipamorelin, Hexarelin and HCG renders (see above); a 10 mg BPC-157 render.
- Real pen supplier SKUs (the seed creates `PENDING-` placeholder mappings, like the vial site did at launch).
