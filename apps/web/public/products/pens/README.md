# public/products/pens

Web-served pen renders, one per purchasable size, named `<slug>-<size>.<ext>`
with `/` in a blend's size written as `-` (e.g. `glow-bpc-157-tb-500-ghk-10-10-50.jpg`).
Sources are David's as-delivered files in `assets/pen-images/` at the repo
root; the mapping from source filename to product is recorded in
`docs/plans/pens-fork.md`.

`Product.images` for each product is set by
`services/api/app/scripts/seed_pen_catalog.py` (ascending size order); the
card shows the first image, the PDP gallery shows all sizes as thumbnails.
Products with no render render the letter-tile placeholder
(`components/ProductImagePlaceholder.tsx`).

Adding a render: drop the file here with the naming above, add its path to
the product's `images` tuple in the seed script, re-run the seed.
