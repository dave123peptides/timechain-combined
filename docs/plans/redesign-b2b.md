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

## Second pass, same evening: modern, clean, minimal

David rejected the cream-and-serif pass ("make it more modern ... doctor
focused ... simple doctor can go in there and see all the stuff ... modern
clean minimalistic look"). The direction now:

- **Palette**: white, `#f6f7f9` surface, near-black `#0f1419` type, thin
  `#e6e8ec` lines, one teal accent `#0f766e`. No ticker, no pedestal art,
  no serif.
- **Type**: Inter Tight for headings (600, -0.03em), labels, nav and
  buttons; Inter for body. A headline's `<em>` is its quiet gray clause.
- **The catalog is an order sheet**: one row per compound with
  thumbnail, name, chemistry line, format badges, a configuration select
  ("10mg · Pen", pens first), a quantity field (default 10) and Add, so a
  practice orders without leaving the list. A grid of cards remains as
  `?view=grid` for when images matter (David: "about the images later").
- **Homepage**: hero with a live slice of the sheet (first promotable
  rows), a four-fact row, the full sheet, three steps, quality, FAQ.
- Images are de-emphasized until David sorts them: 52px thumbnails in
  the sheet, no hero photography.

## Third pass (2026-10-23): see the different peptides

David liked the minimal pass but the sheet was "a little too much of what
do I do, what's here". Now the default catalog view is cards grouped
under their category headings (lib/categories.ts `groupByCategory`: each
compound under the first group that lists it, BAC water under Supplies),
each card with a generous image, the name, its chemistry line, formats
and strengths on two quiet lines, and ONE button. The configuration
select and quantity appear on the card only after that button is pressed
(ProductCardActions). The hero's right side is the categories as tiles
with counts and two example compounds, linking into the filtered
catalog. The dense sheet remains as `?view=sheet`.

## Booking as the primary action (2026-10-23)

David: "I want a CTA of book a meeting ... I'll have a calendar link ...
they're incentivized to book a meeting so they can review this site".
Book a meeting is now the primary button in the header, hero, how it
works, the request drawer and page, the confirmation page and contact;
the order request is the secondary path. `/book` embeds the calendar
(`NEXT_PUBLIC_BOOKING_URL`, `NEXT_PUBLIC_BOOKING_EMBED`) and states what
the call covers; a homepage section (BookSection) makes the case for it.

## One action only (2026-10-23)

David: "remove the requests part ... remove the add to request, the only
CTA I want is book a meeting and it goes straight to the calendly link".
The storefront's order request flow is gone (drawer, context, /request,
/request/sent, the sheet view, the on-card chooser, /admin/requests) and
so is /book: every Book a meeting button is a plain link to
`NEXT_PUBLIC_BOOKING_URL` (https://cal.com/timechain/30min) in a new tab,
with an email fallback while the link is unset. Cards are informational
with a Details link; the product page keeps Format and Strength as
pickers for the spec rows and ends in the booking button. The API's
order-request endpoints (`/api/v1/order-requests`, `/admin/order-requests`)
remain, tested and unused, in case the flow returns.
