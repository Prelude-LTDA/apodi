"""Compile the Apodi UFO sources into the shipped TTF + WOFF2 files.

  python build_fonts.py --sources sources --out fonts

1. fontmake compiles every source UFO listed in Apodi.designspace to a static TTF
   (unhinted, overlaps removed, production glyph names).
2. The TTF is subset to sources/glyphset.txt (plus component/feature closure), keeping the
   same OpenType features Open Sans ships, plus kerning.
3. A WOFF2 copy is written next to it.
"""
import argparse
import os
import shutil
import subprocess
import sys

import ufoLib2
from fontTools import subset
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.ttLib import TTFont

FEATURES = ["aalt", "rvrn", "ccmp", "case", "dnom", "frac", "liga", "lnum", "locl", "mark", "mkmk",
            "numr", "onum", "ordn", "pnum", "rtlm", "salt", "ss01", "ss02", "ss03", "ss04", "subs",
            "sups", "tnum", "zero", "kern", "dist"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="sources")
    ap.add_argument("--out", default="fonts")
    ap.add_argument("--build", default="build")
    a = ap.parse_args()

    ds = DesignSpaceDocument.fromfile(os.path.join(a.sources, "Apodi.designspace"))
    ufos = [os.path.join(a.sources, s.filename) for s in ds.sources]
    full = os.path.join(a.build, "ttf-full")
    os.makedirs(full, exist_ok=True)
    subprocess.run([sys.executable, "-m", "fontmake", "-u", *ufos, "-o", "ttf",
                    "--output-dir", full, "--overlaps-backend", "pathops"], check=True)

    keep_names = [l.strip() for l in open(os.path.join(a.sources, "glyphset.txt"))
                  if l.strip() and not l.startswith("#")]
    os.makedirs(os.path.join(a.out, "ttf"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "woff2"), exist_ok=True)
    for ufo_path in ufos:
        ufo = ufoLib2.Font.open(ufo_path, lazy=True)
        ps = ufo.info.postscriptFontName
        prod = ufo.lib.get("public.postscriptNames", {})
        src = os.path.join(full, f"{ps}.ttf")
        font = TTFont(src)
        order = set(font.getGlyphOrder())
        glyphs = sorted({prod.get(n, n) for n in keep_names} & order)
        opts = subset.Options()
        opts.layout_features = FEATURES
        opts.name_IDs = ["*"]
        opts.name_legacy = True
        opts.name_languages = ["*"]
        opts.glyph_names = True
        opts.notdef_outline = True
        opts.recalc_bounds = True
        opts.recalc_average_width = True
        opts.drop_tables = []
        opts.hinting = False
        sub = subset.Subsetter(opts)
        sub.populate(glyphs=glyphs + [".notdef"])
        sub.subset(font)
        font["hhea"].advanceWidthMax = max(adv for adv, _ in font["hmtx"].metrics.values())
        ttf = os.path.join(a.out, "ttf", f"{ps}.ttf")
        font.save(ttf)
        font = TTFont(ttf)
        font.flavor = "woff2"
        font.save(os.path.join(a.out, "woff2", f"{ps}.woff2"))
        print(ttf, len(font.getGlyphOrder()), "glyphs")


if __name__ == "__main__":
    main()
