"""Extract ONLY numeric metrics from a reference font into JSON.

Reads: per-codepoint advance widths, vertical metrics, weight class, x-height,
cap height, italic angle, kerning pair values keyed by codepoint pairs, and the bounding boxes
of the box-drawing and integral-piece characters (which must join across lines).
No outline, point, curve or glyph-name data is read or written.

Usage: python -I extract_metrics.py <reference.ttf> <out.json>
"""
import json
import sys

from fontTools.ttLib import TTFont


def main(src, dst):
    f = TTFont(src)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"].metrics
    rev = {}
    for cp, g in cmap.items():
        rev.setdefault(g, []).append(cp)

    adv = {cp: hmtx[g][0] for cp, g in cmap.items()}

    # Default-on ligatures (liga): recorded only as "character sequence -> advance".
    ligs = {}
    gsub = f["GSUB"].table
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag != "liga":
            continue
        for li in fr.Feature.LookupListIndex:
            for st in gsub.LookupList.Lookup[li].SubTable:
                st = getattr(st, "ExtSubTable", st)
                if not hasattr(st, "ligatures"):
                    continue
                for first, lst in st.ligatures.items():
                    for lig in lst:
                        comps = [first] + list(lig.Component)
                        if all(rev.get(c) for c in comps):
                            seq = "".join(chr(min(rev[c])) for c in comps)
                            ligs.setdefault(seq, hmtx[lig.LigGlyph][0])
                            rev.setdefault(lig.LigGlyph, []).append(seq)
    os2, hhea, head = f["OS/2"], f["hhea"], f["head"]
    vm = dict(
        unitsPerEm=head.unitsPerEm,
        hheaAscender=hhea.ascent, hheaDescender=hhea.descent, hheaLineGap=hhea.lineGap,
        typoAscender=os2.sTypoAscender, typoDescender=os2.sTypoDescender,
        typoLineGap=os2.sTypoLineGap, winAscent=os2.usWinAscent, winDescent=os2.usWinDescent,
        xHeight=os2.sxHeight, capHeight=os2.sCapHeight, weightClass=os2.usWeightClass,
        widthClass=os2.usWidthClass, italicAngle=f["post"].italicAngle,
        useTypoMetrics=bool(os2.fsSelection & (1 << 7)),
    )

    # Kerning: GPOS 'kern' feature PairPos lookups, flattened to codepoint pairs.
    # Precedence follows OpenType: first subtable covering a pair wins.
    pairs = {}
    gpos = f["GPOS"].table
    kern_lookups = sorted({i for fr in gpos.FeatureList.FeatureRecord
                           if fr.FeatureTag == "kern" for i in fr.Feature.LookupListIndex})
    flags = set()
    for li in kern_lookups:
        lk = gpos.LookupList.Lookup[li]
        flags.add(lk.LookupFlag)
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if st.LookupType != 2 if hasattr(st, "LookupType") else False:
                continue
            seen_first = set()
            if st.Format == 1:
                for g1, ps in zip(st.Coverage.glyphs, st.PairSet):
                    for pvr in ps.PairValueRecord:
                        v = getattr(pvr.Value1, "XAdvance", 0) if pvr.Value1 else 0
                        for c1 in rev.get(g1, []):
                            for c2 in rev.get(pvr.SecondGlyph, []):
                                pairs.setdefault((c1, c2), v)
            elif st.Format == 2:
                cd1 = st.ClassDef1.classDefs
                cd2 = st.ClassDef2.classDefs
                all_glyphs = [g for g in rev]
                for g1 in st.Coverage.glyphs:
                    k1 = cd1.get(g1, 0)
                    row = st.Class1Record[k1].Class2Record
                    for g2 in all_glyphs:
                        k2 = cd2.get(g2, 0)
                        rec = row[k2]
                        v = getattr(rec.Value1, "XAdvance", 0) if rec.Value1 else 0
                        for c1 in rev.get(g1, []):
                            for c2 in rev.get(g2, []):
                                # A format-2 subtable that covers g1 claims the pair
                                # even with zero value (HarfBuzz behaviour).
                                pairs.setdefault((c1, c2), v)
    kern = [[a, b, v] for (a, b), v in sorted(pairs.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))) if v]
    # Bounding boxes (numbers only) of the characters that must join their neighbours across
    # lines: box drawing and the integral pieces.
    glyf = f["glyf"] if "glyf" in f else None
    bnds = {}
    for cp in list(range(0x2500, 0x2580)) + [0x2320, 0x2321]:
        if glyf is not None and cp in cmap:
            g = glyf[cmap[cp]]
            if hasattr(g, "xMin"):
                bnds[str(cp)] = [g.xMin, g.yMin, g.xMax, g.yMax]
    out = dict(source_file=src.split("/")[-1], vertical=vm, bounds=bnds,
               advances={str(k): v for k, v in sorted(adv.items())},
               ligatures=ligs,
               kern_lookup_flags=sorted(flags), kerning=kern)
    with open(dst, "w") as fh:
        json.dump(out, fh)
    print(dst, len(adv), "codepoints", len(kern), "kern pairs", "flags", flags)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
