"""Contact sheet of the characters drawn from Noto (the ones Open Sans lacks).

  python -I scripts/added_glyphs.py --fonts fonts/ttf --out docs/images/added-glyphs.png
  python -I scripts/added_glyphs.py --fonts fonts/ttf --aptos APTOS_DIR --out docs/comparison/added-glyphs-reference.png

Per style: the glyphs in a grid with their codepoints, then a box drawn with box-drawing
characters and an integral built from its two halves, set at the font's own line height (the
lines must join). With --aptos, a reference row is drawn above each Apodi row: that sheet
contains reference renderings, so keep it local (docs/comparison/ is git-ignored).
"""
import argparse
import os
import sys

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from noto_glyphs import SOURCES  # noqa: E402

STYLES = [("Apodi-Regular", "Aptos.ttf"), ("Apodi-Bold", "Aptos Bold.ttf"),
          ("ApodiNarrow-Bold", "Aptos Narrow Bold.ttf"), ("Apodi-Italic", "Aptos Italic.ttf")]
SIZE = 56
PER_ROW = 21
CELL = 92
BOX = ["┌────┐ ┌┐ ⌠", "└────┘ ││ ⌡", "┌────┐ └┘", "└────┘"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="fonts/ttf")
    ap.add_argument("--aptos", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cps = sorted(SOURCES)
    lab = ImageFont.truetype(os.path.join(a.fonts, "Apodi-Regular.ttf"), 14)
    head = ImageFont.truetype(os.path.join(a.fonts, "Apodi-Regular.ttf"), 22)
    blocks = []
    for stem, ref in STYLES:
        path = os.path.join(a.fonts, stem + ".ttf")
        have = TTFont(path).getBestCmap()
        sources = [("Apodi", path)]
        if a.aptos:
            sources.insert(0, ("Aptos", os.path.join(a.aptos, ref)))
        blocks.append((stem, [c for c in cps if c in have], sources))
    nrows = (len(cps) + PER_ROW - 1) // PER_ROW
    per_src = CELL + 22
    box_h = int(SIZE * 1.25 * len(BOX)) + 30
    block_h = 40 + nrows * per_src * (2 if a.aptos else 1) + box_h + 20
    W = 40 + PER_ROW * CELL
    im = Image.new("RGB", (W, block_h * len(blocks)), "white")
    d = ImageDraw.Draw(im)
    y = 0
    for stem, cs, sources in blocks:
        d.text((20, y + 8), stem + ("  (grey label: reference)" if a.aptos else ""), fill="black", font=head)
        y += 40
        for r in range(nrows):
            row = cs[r * PER_ROW:(r + 1) * PER_ROW]
            for name, p in sources:
                f = ImageFont.truetype(p, SIZE, layout_engine=ImageFont.Layout.RAQM)
                for i, cp in enumerate(row):
                    x = 20 + i * CELL
                    d.rectangle([x, y, x + CELL - 6, y + CELL], outline=(225, 225, 225))
                    d.text((x + 4, y + 2), f"{cp:04X}", fill=(150, 150, 150) if name == "Aptos" else (60, 60, 60), font=lab)
                    d.text((x + 10, y + 18), chr(cp), fill="black", font=f)
                y += per_src
        # box drawing and integral halves at the font's line height: they must join
        bx = 20
        for name, p in sources:
            tt = TTFont(p)
            upm = tt["head"].unitsPerEm
            line = (tt["hhea"].ascent - tt["hhea"].descent + tt["hhea"].lineGap) / upm * SIZE
            f = ImageFont.truetype(p, SIZE, layout_engine=ImageFont.Layout.RAQM)
            for i, t in enumerate(BOX):
                d.text((bx, y + 10 + i * line), t, fill="black", font=f)
            bx += int(f.getlength(BOX[0])) + 60
        y += box_h + 20
    im.crop((0, 0, W, y)).save(a.out)


if __name__ == "__main__":
    main()
