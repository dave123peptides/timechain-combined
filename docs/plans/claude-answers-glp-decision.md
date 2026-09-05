# FINAL ANSWERS TO ALL FOUR QUESTIONS — GLP DECISION RESOLVED

**Context: this decision was made by David with enforcement research in hand (April 2026 FDA warning-letter batch hit three vendors using our exact code-name scheme — PekCura "GLP-1-S/2-T/3-R", Pink Pony "GLP-2 TZ / GLP-3 RT", Gram "GLP-1-R peptide"). Strategy: the BioLongevity Labs survivor pattern — sellable but quiet, research-tethered copy, zero consumer-demand signaling.**

## Q1: Are the four GLP-class products (glp-1s, glp-2t, glp-3r, cagrilinitide) in or out of public sale?

**ANSWER: IN — sellable, but "de-clawed" (BioLongevity pattern). Custom answer, not one of the offered options:**

Keep all four purchasable on /shop. But apply ALL of the following, non-negotiable:

1. **Strip the mechanism taglines from product copy.** The current description/content for these four ("triple GIP/GLP-1/glucagon receptor agonist", "dual GIP/GLP-1", "amylin receptor agonist", any receptor-agonism language in marketing voice) MUST be replaced with research-neutral copy. Pattern: "A metabolic-pathway research compound. Receptor activity and published literature are described in the research sections of this page." Receptor discussion is acceptable ONLY inside research-areas/overview framed as "studied for/investigated in", never as product marketing. NEVER reference weight loss, appetite, fat loss, body composition, or any human outcome. NEVER map to drug names (retatrutide/tirzepatide/semaglutide/cagrilintide) anywhere public.
2. **No promotion anywhere:** excluded from the hero spotlight, featured sections, category nav highlighting, "best seller"/"popular" badges, and search suggestions. They sit in /shop, findable by people who already know the name, invisible to browsers. (Direct search for the slug/code-name still works — deliberate.)
3. **Rewrite the four entries in sync_product_content.py's _CONTENT before running any backfill** (Claude already committed to this — confirmed as required, not optional).
4. **pairs_with links among GLP products:** keep (research framing, not promotion).
5. **Flag the four rewritten product pages for attorney (Janesa) review before public launch** — add a TODO comment in the code and list it in the final summary.

## Q2: What should the hero spotlight feature?

**ANSWER: BPC-157** (slug `bpc-157` — sellable, 2 variants at $79/$149, has 2 images). It's compliance-clean, one of the most-recognized research peptides, and already our most cross-linked product. Quality-first hero copy per the existing compliance pattern. (GLP-3R is excluded per Q1 rule 2 — the demand exists, but the hero spotlight is precisely the "consumer-demand signaling" the FDA letters quoted.)

## Q3: Which taxonomy do I actually build?

**ANSWER: The script's six (option 2)** — from `services/api/app/scripts/sync_lyo_catalog.py` `_CATEGORY`:
**GLP-1 & Metabolic / Growth Hormone & Recovery / Healing & Repair Blends / Longevity & Cognitive / Sexual Health & Hormonal / Supplies.**

Reasons: (a) the slug→category mapping already exists for all 32 sellable products with zero gaps — no authoring round-trip, no approval delay; (b) David already approved this mapping when the script was written (2026-08-22/23 decisions); (c) it's more specific than the agent's five. Run the sync (or an alembic data migration mirroring it) to apply.

**Plus this rule:** the GLP-1 & Metabolic category pill may show in nav (it has sellable products) but the four GLP products get NO additional visual emphasis within it (no badges, no ordering to front, alphabetical/default order only).

## Q4: Contact page in v1 — no email infrastructure exists?

**ANSWER: Option 1 — mailto link, no form (Claude's recommendation, confirmed).** Contact page publishes `support@timechainpeptides.com` as a mailto link plus the business address (Timechain Ventures LLC, Florida — street address TBD from David, use "Florida, USA" placeholder). Zero new infrastructure, nothing to break, works the moment the mailbox exists. If a form is wanted later, it needs a provider decision (Resend/SES) — NOT v1 scope.

---

## Standing rules recap (unchanged, now with the GLP decision folded in)

- Real claims only — no fabricated counts/scores/testimonials; no purity % until third-party data exists.
- GLP class (glp-1s, glp-2t, glp-3r, cagrilinitide) + literal-name rows (retatrutide/semaglutide/tirzepatide): the literal-name rows stay is_sellable=false forever; the four code-names stay sellable but de-clawed per above.
- Never surface drug names (retatrutide/tirzepatide/semaglutide/cagrilintide/Ozempic/Wegovy/Mounjaro/Zepbound) anywhere public — nav, search, copy, meta tags, alt text.
- No MPA server actions in apps/web (Next 15.5 prod bug). Route handlers only.
- Don't touch checkout/payment flow, /enter gate, /age-gate.
- No `<form>` contact infrastructure in v1 (mailto only).
- Mobile-first, 375px verified. npm build/typecheck/lint + API pytest all green before finishing.
- Deploys: push to GitHub and stop — Hermes agent runs `vercel deploy --prod` and live QA.
- BAC water: stays sellable for v1 (it's a standard research supply), but flagged as a pre-launch discussion item with attorney (the FDA letters cite bac-water pairing as intent evidence — Janesa should rule on whether it stays on the public storefront at launch).

---

## Pens site (TCP) addendum — David, 2026-09-05

For the pens storefront the four GLP-class products keep their code-name
slugs (`glp-1s`, `glp-2t`, `glp-3r`, `cagrilinitide`) and every rule above
(no promotion, no outcome language, `UNPROMOTED_SLUGS` in
`lib/compliance.ts`), but the **display name carries the real name in
parentheses** — "GLP-1S (Semaglutide)", "GLP-2T (Tirzepatide)", "GLP-3R
(Retatrutide)", "Cagrilinitide (Cagrilintide)" — set in
`services/api/app/scripts/seed_pen_catalog.py`. The pen renders also print
"Each unit contains … Semaglutide" on the label. This departs from the
"never surface drug names" rule above and is flagged `TODO(attorney-review)`
in the seed script and `compliance.ts`.

Size labels stay strength-only ("1.5mg"); the price sheet's "Month N"
tiers are never printed publicly (they read as a titration schedule) and
live only on the placeholder supplier rows for fulfillment.
