# Combined site redesign: B2B (2026-10-22)

David's brief, verbatim intent: "complete redesign ... focuses for b2b
targeting researchers/medical practices ... stick with no pricing and
focused for ordering multi-quantity. ill give you pricing soon." References:
realpeptides.co, biolongevitylabs.com, otmens.com, otmenshealth.com,
ascendbioslabs.com, americanpeptides.us.

## What the references share (observed 2026-10-22)

- OT / Overtime Men's Health: warm cream paper, large serif headlines with
  one italic accent word in gold, floating pill navigation, eyebrow-labelled
  cards, product shots on stone pedestals with small codes, a ticker of
  facts (licensed, compounded in U.S. pharmacies), stats row.
- Ascend Bio Labs: deep navy, serif "Every vial. Verified.", three-step
  "how a vial reaches you", a COA card you can read before buying, a
  volume incentive ("the more you stock...").
- BioLongevity Labs: five-point trust strip, stat tiles, three independent
  labs, open COA library, "USA manufactured".
- Real Peptides: cream and gold, "Build a Pack" multi-quantity, Wholesale
  in the nav, best sellers, "every batch, independently verified".
- American Peptides: ticker bar, category chips with counts, catalog
  sectioned by category, Wholesalers and Partner Program links.

## Direction

- **Palette**: paper `#f7f4ee`, surface `#f1ede4`, ink navy `#15213a`,
  brass accent `#b4893a` / deep `#8f6b26`. The `--gold*` token names are
  finally literal.
- **Type**: Instrument Serif for display (400, with italic for the accent
  word), Inter for body, Inter Tight for uppercase labels and nav.
- **Audience**: research organizations and medical practices. Hero and
  contact copy say so; RUO disclaimers stay on every product page and in
  the footer. TODO(attorney-review): "medical practices" next to
  research-use-only language.
- **No prices**: `CATALOG_PRICES_PUBLIC` (API) nulls every price field;
  `NEXT_PUBLIC_PRICING_VISIBLE` (web) decides whether to render them.
  Both off until the wholesale sheet exists.
- **Multi-quantity ordering without payment**: an order request. Every
  card and product page adds a format, strength and quantity to a request
  list (localStorage, like the old cart); `/request` collects contact
  details and POSTs to `/api/v1/order-requests`, which stores an immutable
  snapshot and forwards it to `ORDER_REQUEST_WEBHOOK_URL` (a GHL inbound
  webhook). `/admin/requests` lists them. Booking a meeting stays as the
  secondary path on /contact.
- **Structure**: facts ticker, floating header (Catalog, Pens, Vials,
  Quality, Contact; search; Request list), hero, live stats strip, how
  ordering works, catalog with the Pens | Vials toggle and category pills,
  quality section, formats section, FAQ, request call-to-action band,
  four-column footer.

## Out of scope for now

Pricing and volume tiers (sheet to come), accounts or wholesale logins,
a CMS, blog or learn section, any payment.
