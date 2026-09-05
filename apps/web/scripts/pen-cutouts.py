"""Transparent cut-outs of pen renders for the homepage hero and the shop
banner. The catalog renders under public/products/pens/ are JPEGs of a
horizontal pen on a pure-white ground with a soft shadow beneath; the
hero floats its pens on a light gradient, so the ground has to go.

A luminance flood fill cannot do it: the pen's white upper body is the
same white as the ground, separated only by a 252-luminance top edge.
So the mask is geometric instead. The pen is horizontal and straight, so
its top edge is at one row for every column; that row is found as the
median first-non-white row across the pen's columns. Its bottom edge is
per column: the last row of the dark lower body. Between the two the
pen is opaque; below it the render's own shadow becomes a translucent
dark shadow (alpha from how far the pixel is from white); everything
else is clear.

Run from apps/web with Pillow available (the API venv has it):
    ../../services/api/.venv/bin/python scripts/pen-cutouts.py
Outputs public/products/hero/<slug>.png. Only promotable products belong
in the hero (lib/compliance.ts) — see public/products/hero/README.md.
"""

from pathlib import Path
from statistics import median

from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
PRODUCTS = HERE.parent / "public" / "products"
PAIRS = {
    "bpc-157": "pens/bpc-157-20.jpg",
    "tb-500": "pens/tb-500-10.jpg",
    "ghk-cu": "pens/ghk-cu-50.jpg",
}
EDGE = 253  # the pen's faint top edge: first row at/below this luminance
DARK = 205  # the pen's shaded lower body ends at the last row below this
SHADOW_RANGE = 60  # luminance span (255 → 195) mapped onto shadow alpha 0 → 255
SHADOW_RGB = (20, 21, 26)


def cutout(src: Path, dst: Path) -> None:
    image = Image.open(src).convert("RGBA")
    width, height = image.size
    lum = image.convert("L").load()
    pixels = image.load()

    bottoms: list[int | None] = []
    tops: list[int] = []
    for x in range(width):
        column = [lum[x, y] for y in range(height)]
        dark_rows = [y for y, v in enumerate(column) if v < DARK]
        bottoms.append(max(dark_rows) if dark_rows else None)
        if dark_rows:
            tops.append(next(y for y, v in enumerate(column) if v <= EDGE))
    top = int(median(tops)) - 1

    alpha = Image.new("L", (width, height), 0)
    alpha_px = alpha.load()
    for x in range(width):
        bottom = bottoms[x]
        for y in range(height):
            if bottom is not None and top <= y <= bottom:
                alpha_px[x, y] = 255
            elif bottom is None or y > bottom:
                shade = (255 - lum[x, y]) * 255 // SHADOW_RANGE
                if shade > 0:
                    alpha_px[x, y] = min(255, shade)
                    pixels[x, y] = (*SHADOW_RGB, 255)
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.5))
    image.putalpha(alpha)
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst, optimize=True)
    print(f"{src.name} -> {dst.relative_to(HERE.parent)} top={top} body rows≈{top}-{max(b for b in bottoms if b)}")


if __name__ == "__main__":
    for slug, rel in PAIRS.items():
        cutout(PRODUCTS / rel, PRODUCTS / "hero" / f"{slug}.png")
