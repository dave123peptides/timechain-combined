# public/products/hero

Cut-out pen renders (transparent background, landscape 830x195) for the
homepage hero (`components/home/HomeHero.tsx`) and the shop banner
(`app/(storefront)/shop/page.tsx` via `PageBanner`).

Generated from the catalog renders in `../pens/` by
`apps/web/scripts/pen-cutouts.py` (border-connected light pixels become
transparent; the render's soft shadow survives as a translucent shadow):

```sh
cd apps/web
../../services/api/.venv/bin/python scripts/pen-cutouts.py
```

Only promotable products belong here (`lib/compliance.ts`): never a
GLP-class code-name product. Current set: `bpc-157.png`, `tb-500.png`,
`ghk-cu.png`.
