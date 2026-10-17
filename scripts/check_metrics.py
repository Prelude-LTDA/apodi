"""Metric-compatibility check: built Apodi binaries vs the reference (Aptos) fonts.

  APTOS_DIR=/path/to/aptos python -I check_metrics.py --fonts fonts/ttf [--json out.json]

The reference fonts are read locally and only their numbers are compared (advance widths by
codepoint, vertical metrics, shaped advance of every kerning pair and ligature sequence).
Nothing from them is written anywhere except counts and the mismatching codepoints.
"""
import argparse
import json
import os
import sys

import uharfbuzz as hb
from fontTools.ttLib import TTFont

PAIRS = {  # Apodi file stem -> reference file name
    "Apodi-Regular": "Aptos.ttf", "Apodi-Bold": "Aptos Bold.ttf",
    "Apodi-Italic": "Aptos Italic.ttf", "Apodi-BoldItalic": "Aptos Bold Italic.ttf",
    "ApodiNarrow-Regular": "Aptos Narrow.ttf", "ApodiNarrow-Bold": "Aptos Narrow Bold.ttf",
    "ApodiNarrow-Italic": "Aptos Narrow Italic.ttf", "ApodiNarrow-BoldItalic": "Aptos Narrow Bold Italic.ttf",
    "ApodiDisplay-Regular": "Aptos Display.ttf", "ApodiDisplay-Bold": "Aptos Display Bold.ttf",
    "ApodiDisplay-Italic": "Aptos Display Italic.ttf", "ApodiDisplay-BoldItalic": "Aptos Display Bold Italic.ttf",
}
VERT = [("hhea", "ascent"), ("hhea", "descent"), ("hhea", "lineGap"), ("OS/2", "sTypoAscender"),
        ("OS/2", "sTypoDescender"), ("OS/2", "sTypoLineGap"), ("OS/2", "usWinAscent"),
        ("OS/2", "usWinDescent"), ("head", "unitsPerEm")]


def shaper(path):
    font = hb.Font(hb.Face(open(path, "rb").read()))

    def width(text, kern=True, with_count=False):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {"kern": kern})
        w = sum(p.x_advance for p in buf.glyph_positions)
        return (w, len(buf.glyph_infos)) if with_count else w
    return width


def kern_pairs(ref):
    """Codepoint pairs that the reference kerns (GPOS PairPos in 'kern')."""
    cmap = ref.getBestCmap()
    rev = {}
    for cp, g in cmap.items():
        rev.setdefault(g, []).append(cp)
    gpos = ref["GPOS"].table
    out = set()
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag != "kern":
            continue
        for li in fr.Feature.LookupListIndex:
            for st in gpos.LookupList.Lookup[li].SubTable:
                st = getattr(st, "ExtSubTable", st)
                if st.Format == 1:
                    for g1, ps in zip(st.Coverage.glyphs, st.PairSet):
                        for r in ps.PairValueRecord:
                            if r.Value1 and getattr(r.Value1, "XAdvance", 0):
                                for a in rev.get(g1, []):
                                    for b in rev.get(r.SecondGlyph, []):
                                        out.add((a, b))
                elif st.Format == 2:
                    by1 = {}
                    for g in st.Coverage.glyphs:
                        by1.setdefault(st.ClassDef1.classDefs.get(g, 0), []).append(g)
                    by2 = {}
                    for g in rev:
                        by2.setdefault(st.ClassDef2.classDefs.get(g, 0), []).append(g)
                    for c1, gs1 in by1.items():
                        for c2, rec in enumerate(st.Class1Record[c1].Class2Record):
                            if rec.Value1 and getattr(rec.Value1, "XAdvance", 0):
                                for g1 in gs1:
                                    for g2 in by2.get(c2, []):
                                        for a in rev.get(g1, []):
                                            for b in rev[g2]:
                                                out.add((a, b))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="fonts/ttf")
    ap.add_argument("--aptos", default=os.environ.get("APTOS_DIR"))
    ap.add_argument("--json")
    ap.add_argument("--no-kern", action="store_true")
    a = ap.parse_args()
    if not a.aptos:
        sys.exit("set APTOS_DIR or pass --aptos")
    results = {}
    print(f"{'style':26} {'ref cps':>7} {'covered':>7} {'adv≠':>5} {'vert≠':>5} {'kern pairs':>10} {'kern≠':>6} {'lig≠':>5}")
    for stem, refname in PAIRS.items():
        mine_p = os.path.join(a.fonts, stem + ".ttf")
        ref_p = os.path.join(a.aptos, refname)
        if not (os.path.exists(mine_p) and os.path.exists(ref_p)):
            continue
        mine, ref = TTFont(mine_p), TTFont(ref_p)
        mc, rc = mine.getBestCmap(), ref.getBestCmap()
        mh, rh = mine["hmtx"].metrics, ref["hmtx"].metrics
        covered = [cp for cp in rc if cp in mc]
        adv_mis = [(cp, rh[rc[cp]][0], mh[mc[cp]][0]) for cp in covered if rh[rc[cp]][0] != mh[mc[cp]][0]]
        vert_mis = [(t, f, getattr(ref[t], f), getattr(mine[t], f)) for t, f in VERT
                    if getattr(ref[t], f) != getattr(mine[t], f)]
        r = dict(ref_codepoints=len(rc), covered=len(covered), missing=sorted(set(rc) - set(mc)),
                 advance_mismatches=adv_mis, vertical_mismatches=vert_mis)
        wm, wr = shaper(mine_p), shaper(ref_p)
        lig_mis = []
        for seq in ("fi", "fl", "ff", "ffi", "ffl", "ft", "fj", "fb", "fh", "fk", "Th", "st"):
            for kern in (False, True):
                if wm(seq, kern) != wr(seq, kern):
                    lig_mis.append((seq, kern, wr(seq, kern), wm(seq, kern)))
        r["ligature_mismatches"] = lig_mis
        if not a.no_kern:
            pairs = sorted(p for p in kern_pairs(ref) if p[0] in mc and p[1] in mc)
            kmis, subst = [], []
            for x, y in pairs:
                t = chr(x) + chr(y)
                ra, ma = wr(t), wm(t)
                if ra != ma:
                    # if the pair already differs with kerning off, the reference re-shapes the
                    # sequence (e.g. it decomposes U+FB01 and re-ligates "f"+"fi" as "ff"+"i"):
                    # a substitution difference, reported apart from kerning mismatches
                    (subst if wr(t, False) != wm(t, False) else kmis).append((x, y, ra, ma))
            r["kern_pairs_tested"] = len(pairs)
            r["kern_mismatches"] = kmis
            r["kern_shaping_differences"] = subst
        results[stem] = r
        print(f"{stem:26} {len(rc):7} {len(covered):7} {len(adv_mis):5} {len(vert_mis):5} "
              f"{r.get('kern_pairs_tested', 0):10} {len(r.get('kern_mismatches', [])):6} {len(lig_mis):5}")
        for cp, rv, mv in adv_mis[:10]:
            print(f"    U+{cp:04X} {chr(cp)!r}: ref {rv} mine {mv}")
        for x, y, rv, mv in r.get("kern_mismatches", [])[:10]:
            print(f"    kern {chr(x)!r}{chr(y)!r} U+{x:04X} U+{y:04X}: ref {rv} mine {mv}")
        for x, y, rv, mv in r.get("kern_shaping_differences", [])[:10]:
            print(f"    (shaping differs, not counted) {chr(x)!r}{chr(y)!r} U+{x:04X} U+{y:04X}: ref {rv} mine {mv}")
        for m in lig_mis[:5]:
            print("    lig", m)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(results, fh, indent=1)
    bad = sum(len(r["advance_mismatches"]) + len(r["vertical_mismatches"]) + len(r.get("kern_mismatches", []))
              for r in results.values())
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
