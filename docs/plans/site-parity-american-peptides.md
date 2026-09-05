# Plan: Bring Timechain Peptides to par with americanpeptides.us

Reference site: https://americanpeptides.us/ — a polished Shopify-style peptide storefront.
Ours: Next.js 15 App Router (`apps/web`) + FastAPI (`services/api`), products served from
Postgres via `/shop/products`. This plan is what Claude Code should implement, in priority
order. Anything marked **DAVID** is an asset/decision only David can provide — code cannot
create it.

## Ground truth about our current site (read this first)

- Products live in Postgres (`products` table), served by the API. 72 products / 211 variants;
  **35 products have zero images**, 16 have one, 21 have 2+.
- `products.images` is a JSONB array of paths like `/products/bpc-157-1.jpg` — these are
  **relative paths that serve from `apps/web/public/products/`** (55 files there today).
  The live site is `timechain-storefront.vercel.app`; the API is `timechain-api.vercel.app`.
- Categories today are only 3: RUO Lyophilized / RUO Pens / RUO Vials.
- Existing components: `Hero`, `FeaturedProducts`, `CategoryNav`, `TrustBar`,
  `ProductCard`, `ProductGallery`, `Header`, `Footer`, `FormatNotice`.
- Middleware gates: `/enter` password lock → `/age-gate`. Keep both working.
- **Do not use Next.js MPA server actions (`<form action={fn}>`) anywhere** — they 500 in
  production builds on Next 15.5 (verified). Use route handlers or client fetches.

---

## Phase 1 — Visual polish of what exists (pure frontend, no new data needed)

### 1.1 Announcement bar (top of every page, above header)
Scrolling/marquee or rotating single-line bar like American Peptides'. Content **DAVID
decides** (suggested, must all be TRUE before launch):
- "USA Sourced · USA Shipped" • "Free Shipping Over $X" • "COA Available Per Lot"
Component: `apps/web/src/components/AnnouncementBar.tsx`, rendered in
`(storefront)/layout.tsx`. CSS animation for marquee; respect `prefers-reduced-motion`.

### 1.2 Hero section upgrade
Current hero is text-only. Build:
- Full-width background image or subtle looping video (`<video autoplay muted loop
  playsinline>` — NO autoplay audio). **DAVID: provide hero image/video file** (see list at
  bottom). Until an asset arrives, implement with a dark gradient + optional static image.
- Overlay stats row like theirs (99%+ purity / lots tested / researchers served) —
  **DAVID: these numbers must be real**. Until real ones exist, show only claims we can
  make (e.g. "Every lot documented", "US-sourced", "Bitcoin accepted").
- Featured-product spotlight (their Retatrutide block): pull the first sellable product
  from `/shop/products` with a large image, "from $X", and CTA. Make the featured slug an
  env var or constant (suggest: our best-seller-to-be).

### 1.3 Category navigation strip
Horizontal pill nav under the header (sticky), like theirs: All Products / GLP-1 &
Metabolic / Research Peptides / Blends / etc. Our data model: `products.category` is a
free string — see Phase 3.1 for the category taxonomy rework; the nav should read
categories from `/shop/filter-options`.

### 1.4 Product card polish
`ProductCard.tsx` currently: image, name, "From $X". Add:
- Badge slot (e.g. "COA Available", "Best Seller", "New") — empty for now, wired for later.
- Category label under the name (like their "GLP-1 Peptide" tag).
- Hover state: second image swap if `images[1]` exists (we already have `images` array).
- "Add to Cart" button ON the card (client component; cart context exists at
  `src/lib/cart-context.tsx`) — currently you must open the PDP to add.

### 1.5 Product page (PDP) polish
Already has gallery, variant picker, FAQ, research areas, pairs-with. Add:
- Quantity selector.
- Sticky buy box on desktop.
- Trust badges row under add-to-cart (reuse `TrustBar compact`).
- "Free shipping threshold" progress bar in cart drawer (**DAVID: confirm the free-shipping
  threshold and whether we offer it at all** — currently flat rate in `system_settings`).

### 1.6 Footer upgrade
Ours is thin. Build a proper multi-column footer like theirs: Shop links, Support
(Contact, Shipping policy, Returns), Legal (Terms / Privacy / Research Use Only), and the
RUO disclaimer sentence. Pages that don't exist yet → see Phase 4.

### 1.7 Global search
They have site search. Implement a header search that queries
`GET /shop/products?q=...`. **API change needed**: `app/api/shop.py`'s list endpoint
currently only filters by category/format — add case-insensitive name/slug/description
`ilike` search param. Debounced dropdown in `Header.tsx` (client component).

---

## Phase 2 — Trust & conversion content (the biggest gap vs. American Peptides)

Their site sells on VERIFIABLE PROOF: COAs per lot, purity numbers, testing layers,
published SDS files. Ours says "verified sourcing" with no artifacts. This is the single
biggest credibility gap.

### 2.1 COA system (HIGH PRIORITY)
- **DAVID: we need actual COA PDFs** from the supplier per product/lot. If we don't have
  them, we cannot fake this — regulatory exposure. If UMS-RX/NxGen provide COAs, collect
  them.
- Code side (can be built before PDFs arrive): add `coa_url` / `sds_url` (nullable) to the
  `products` table (alembic migration), surface as buttons on the PDP, and a central
  `/coa` page listing all products with their documents (mirror their /pages/coa).
  Empty state: "COA available on request — email support@timechainpeptides.com".

### 2.2 "Why Timechain" standards section
Rebuild `TrustBar` into a full section like their "A Standard You Can Verify": Analytical
Purity / COA On Every Lot / US Sourcing+Shipping — with the same real-claims-only rule.
**DAVID: confirm which claims are true today** (US compounding 503a, same-day ship cutoff,
etc.) — see question list at bottom.

### 2.3 FAQ section on homepage
Port their FAQ structure with our honest answers: shipping times, storage guidance,
RUO meaning, Bitcoin payment how-to, COA policy. 6–8 questions, accordion component.

### 2.4 Shipping policy page (new `/shipping`)
Cut-off time, carriers, packaging, free-shipping threshold if any, international=US-only.
**DAVID: supply the business facts** (cutoff time, carrier, processing time).

### 2.5 Contact page (new `/contact`)
Email (support@timechainpeptides.com), hours, simple form → API route that logs to a
`contact_messages` table or just sends email. **DAVID: decide where contact form
submissions go** (email inbox vs. admin dashboard).

### 2.6 About page beef-up
`(storefront)/about` exists — expand with sourcing story, US-compounding angle, the
pen/liquid multi-mL differentiators (from brand strategy).

---

## Phase 3 — Catalog structure (API + data work)

### 3.1 Category taxonomy rework
Today: 3 flat strings. They have 9 meaningful collections (GLP-1 & Metabolic, Research
Peptides, Blends, Bundles, Bioregulators, Lab Supplies...). Plan:
- Define our taxonomy (suggest): GLP-1 & Metabolic / Research Peptides / Peptide Blends /
  Bioregulators / Lab Supplies / Bundles. **DAVID: approve the taxonomy** — it drives nav,
  home sections, and PDP tags.
- Add a migration + admin mapping to recategorize the 72 existing products.
- `/shop` page: category sidebar/section anchors like their catalog (`#cat-glp-1` style).

### 3.2 Bundles
"Research Bundles" (their 12 bundles) = higher AOV. Our DB has no bundle concept. Lighter
alternative that needs NO schema change: create bundle products as normal products with
multi-variant (e.g. "GLP-1 Starter Bundle"). **DAVID: decide products+pricing for 3–5
launch bundles**; then they're just data rows.

### 3.3 Filter chips + sort on /shop
Category filter exists; add sort (price asc/desc, name A–Z), and format chips. Pure
frontend on top of existing endpoints.

---

## Phase 4 — Missing pages & compliance

- `/shipping` (2.4), `/contact` (2.5), `/faq` (or homepage section).
- `/coa` (2.1 central listing).
- Ensure every page keeps the RUO disclaimer footer + the two gates keep working
  (`/enter`, `/age-gate` — excluded from middleware matcher).

---

## Phase 5 — Nice-to-haves AFTER the above (don't start here)

- Reviews/testimonials (**only real ones; do not fabricate** — DAVID must collect).
- Affiliate page for the 25% program (exists as business plan; site page TBD).
- Email capture (newsletter) — needs ESP choice (DAVID).
- Hero AI video / product 3D spin — DAVID asset question, listed below.

---

## What Claude Code CANNOT do — DAVID's asset/decision list

1. **Product images for the 35 image-less products** (and better images where we have
   only 1): supplier product shots or your own vial photography, consistent background.
   Drop them in `apps/web/public/products/<slug>-1.jpg` etc. and update the DB rows.
2. **Hero background image or short looping video** (AI-generated is fine — e.g. a slow
   macro shot of a vial reconstituting, dark, premium). No audio.
3. **Real stats numbers** for the hero (lots tested, customers served, purity %). Only
   real numbers.
4. **COA/SDS PDFs** from suppliers — or an explicit decision that we say "COA on
   request" instead.
5. **Business facts**: same-day shipping cutoff time? carrier? free-shipping threshold?
   returns policy? where contact-form submissions should go?
6. **Category taxonomy approval** (Phase 3.1 list) + **bundle products/pricing** if wanted.
7. **Featured product** for the hero spotlight — which SKU is our hero?

## Guardrails for Claude Code

- Real claims only — no fabricated counts, review scores, or "verified" claims we can't
  back (TrustBar's docstring already enforces this; keep it).
- No `<form action={serverAction}>` MPA patterns — production 500s (see note above).
- Keep RUO disclaimers on every storefront page (legal requirement, already established).
- Don't touch checkout/payment flow (just stabilized) or the age/access gates.
- Mobile-first: American Peptides is fully responsive; test every section at 375px.
- Verify with `npm run build && npm run typecheck && npm run lint` in `apps/web`, and
  `pytest` in `services/api` for API changes. Deploys are manual via Vercel CLI (no
  auto-deploy from GitHub) — David or the Hermes agent runs `vercel deploy --prod`.
