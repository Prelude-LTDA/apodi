"""Generate the Apodi UFO 3 sources + designspace from the Open Sans sources.

Inputs
  --opensans DIR   Open Sans `sources/` directory (UFO masters + OpenSans-Roman/Italic.designspace),
                   from github.com/googlefonts/opensans (OFL 1.1). The ONLY source of outlines,
                   components, anchors and OpenType substitution features.
  --metrics DIR    ref_<Style>.json files written by extract_metrics.py: numbers only
                   (advance width per codepoint, ligature advance per character sequence,
                   vertical metrics, kerning value per codepoint pair).
  --out DIR        where to write Apodi-*.ufo, Apodi.designspace and fit_report.json.

What it does, per style:
  1. interpolates Open Sans at a grid of widths (wdth 75..100) with the weight compensated so
     the stem thickness stays constant across the grid;
  2. per encoded glyph, takes the grid instance whose natural advance (after scaling the
     outlines so cap height matches the reference) is closest to the reference advance;
     composites and suffixed/ligature glyphs follow their base glyph;
  3. sets the exact advance by moving sidebearings (difference split in proportion to the
     existing left/right sidebearings), with at most +-3% horizontal outline scaling at the
     ends of the width range;
  4. raises the M's middle vertex (design change, parametric on Open Sans's own M);
  5. writes kerning from the reference pair values (class-compressed), drops ligatures the
     reference doesn't form, and sets vertical metrics to the reference numbers.
"""
import argparse
import collections
import copy
import json
import math
import os
import re
import shutil
import statistics
import sys
import time
import unicodedata

import ufoLib2
import uharfbuzz as hb
from fontTools.designspaceLib import (AxisDescriptor, DesignSpaceDocument, DiscreteAxisDescriptor,
                                      InstanceDescriptor, SourceDescriptor)
from fontTools.pens.boundsPen import BoundsPen
from ufo2ft.instantiator import Instantiator

# ----------------------------------------------------------------------------- design parameters
SRC_CAP_HEIGHT = 1462                           # Open Sans cap height (2048 UPM)
WDTH_GRID = [75 + 2.5 * i for i in range(11)]   # 75 .. 100
BASE_WGHT = {"regular": 450, "bold": 700}       # Open Sans user wght at wdth 100 (chosen by eye
                                                # against the reference at equal cap height)
# Beyond the ends of the wdth axis, horizontal outline scaling (with the weight lowered/raised
# so stems keep their thickness) is allowed up to these factors:
STRETCH_WIDE = [1.015, 1.03, 1.045, 1.06]       # at wdth 100
STRETCH_NARROW = [0.985, 0.97]                  # at wdth 75
STRETCH_COST = 0.5                              # 1% of stretch counts like 0.5% of width error
# Open Sans's own alternates promoted to default, where they match the reference's letter
# shapes (checked against renderings): J sitting on the baseline, and in italics the
# double-storey a. The double-storey (binocular) g stays the default, as in the reference.
# The former defaults stay reachable through the same features (salt/ss01/ss03).
DEFAULT_ALTERNATES = {
    "roman": [("J", "J.salt")],
    "italic": [("J", "J.salt"), ("a", "a.ss01")],
}
M_VERTEX_RAISE = 0.16                           # M middle vertex raised by 16% of cap height
VERSION = (1, 0)

STYLES = {
    # key: family, style, italic, weight, Narrow?, Display?, OS/2 width class
    "Regular":           ("Apodi", "Regular", False, "regular", False, False, 5),
    "Bold":              ("Apodi", "Bold", False, "bold", False, False, 5),
    "Italic":            ("Apodi", "Italic", True, "regular", False, False, 5),
    "BoldItalic":        ("Apodi", "Bold Italic", True, "bold", False, False, 5),
    "NarrowRegular":     ("Apodi Narrow", "Regular", False, "regular", True, False, 4),
    "NarrowBold":        ("Apodi Narrow", "Bold", False, "bold", True, False, 4),
    "NarrowItalic":      ("Apodi Narrow", "Italic", True, "regular", True, False, 4),
    "NarrowBoldItalic":  ("Apodi Narrow", "Bold Italic", True, "bold", True, False, 4),
    "DisplayRegular":    ("Apodi Display", "Regular", False, "regular", False, True, 5),
    "DisplayBold":       ("Apodi Display", "Bold", False, "bold", False, True, 5),
    "DisplayItalic":     ("Apodi Display", "Italic", True, "regular", False, True, 5),
    "DisplayBoldItalic": ("Apodi Display", "Bold Italic", True, "bold", False, True, 5),
}

COPYRIGHT = ("Copyright 2020 The Open Sans Project Authors (https://github.com/googlefonts/opensans). "
             "Copyright 2026 The Apodi Project Authors.")
DESCRIPTION = ("An open, metric-compatible alternative to Aptos. Derived from Open Sans "
               "(SIL Open Font License 1.1); see FONTLOG.txt.")
LICENSE = ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
           "This license is available with a FAQ at: https://openfontlicense.org")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def otround(v):
    return int(math.floor(v + 0.5))


# ----------------------------------------------------------------------------- Open Sans access
class OpenSansSpace:
    """One Open Sans designspace (Roman or Italic): interpolation + stem measurement."""

    def __init__(self, ds_path, swaps=()):
        self.swaps = swaps
        self.ds = DesignSpaceDocument.fromfile(ds_path)
        self.ds.instances = []
        self.ds.loadSourceFonts(ufoLib2.Font.open)
        self.inst = Instantiator.from_designspace(self.ds, do_kerning=False)
        self.axes = {a.tag: a for a in self.ds.axes}
        self._cache = {}

    def instance(self, wght, wdth):
        key = (wght, wdth)
        if key not in self._cache:
            d = InstanceDescriptor()
            d.styleName = f"wght{wght}wdth{wdth}"
            d.location = {self.axes["wght"].name: self.axes["wght"].map_forward(wght),
                          self.axes["wdth"].name: self.axes["wdth"].map_forward(wdth)}
            f = self.inst.generate_instance(d)
            for a, b in self.swaps:
                swap_glyphs(f, a, b)
            modify_M(f)
            self._cache[key] = f
        return self._cache[key]

    def stem(self, wght, wdth):
        # stem thickness of "I": horizontal extent minus the slant's contribution in italics
        f = self.instance(wght, wdth)
        bp = BoundsPen(f)
        f["I"].draw(bp)
        x0, y0, x1, y1 = bp.bounds
        return (x1 - x0) - (y1 - y0) * abs(math.tan(math.radians(f.info.italicAngle or 0)))

    def wght_for_stem(self, target, wdth):
        lo, hi = 300.0, 800.0
        for _ in range(14):
            mid = round((lo + hi) / 2 * 4) / 4
            if self.stem(mid, wdth) < target:
                lo = mid
            else:
                hi = mid
        return round((lo + hi) / 2 * 2) / 2


def swap_glyphs(font, a, b):
    """Exchange the drawings (contours, components, anchors, width) of two glyphs; names and
    Unicode values stay, so the alternate becomes the default and vice versa."""
    ga, gb = font[a], font[b]
    da = (list(ga.contours), list(ga.components), list(ga.anchors), ga.width)
    db = (list(gb.contours), list(gb.components), list(gb.anchors), gb.width)
    for g, (cs, comps, anchors, w) in ((ga, db), (gb, da)):
        g.clearContours()
        g.clearComponents()
        g.clearAnchors()
        for c in cs:
            g.appendContour(c)
        for c in comps:
            g.components.append(c)
        for an in anchors:
            g.appendAnchor(an)
        g.width = w
    # composites built on either glyph keep their width relation to the (new) base drawing
    old = {a: da[3], b: db[3]}
    new = {a: db[3], b: da[3]}
    for g in font:
        if (not g.contours and g.components and g.components[0].baseGlyph in old and g.width > 0
                and tuple(g.components[0].transformation)[:4] == (1, 0, 0, 1)):
            base = g.components[0].baseGlyph
            g.width = new[base] + (g.width - old[base])


# ----------------------------------------------------------------------------- design change: M
def modify_M(font):
    """Raise the middle vertex of Open Sans's own M (Mu/Em/M-acute are components of it).

    The two on-curve points of the V's bottom (on the baseline, between the stems) and the
    two points of the inner crotch move up by M_VERTEX_RAISE x cap height; in italics they also
    move along the italic angle so the raise follows the slant.
    """
    g = font["M"]
    pts = [p for c in g.contours for p in c.points]
    base = [p for p in pts if abs(p.y) < 0.5 and p.type]
    xs = sorted(p.x for p in base)
    left_stem_r, right_stem_l = xs[1], xs[-2]
    bottom = [p for p in base if left_stem_r < p.x < right_stem_l]
    assert len(bottom) == 2, ("unexpected M structure", [(p.x, p.y) for p in bottom])
    bx0, bx1 = sorted(p.x for p in bottom)
    cand = sorted((p for p in pts if 0.5 < p.y < 700 and bx0 - 250 < p.x < bx1 + 250),
                  key=lambda p: p.y)[:2]
    assert len(cand) == 2 and abs(cand[0].y - cand[1].y) < 2, "unexpected M crotch"
    angle = font.info.italicAngle or 0
    h = M_VERTEX_RAISE * SRC_CAP_HEIGHT
    dx = -math.tan(math.radians(angle)) * h
    for p in bottom + cand:
        p.x += dx
        p.y += h


# ----------------------------------------------------------------------------- helpers
def first_base(font, name, depth=0):
    g = font[name]
    if g.contours or not g.components or depth > 8:
        return name
    return first_base(font, g.components[0].baseGlyph, depth + 1)


def cmap_of(font):
    cm = {}
    for g in font:
        for u in g.unicodes:
            cm.setdefault(u, g.name)
    return cm


LIGA_RE = re.compile(r"sub\s+((?:[\w.\-]+\s+)+)by\s+([\w.\-]+)\s*;")


def liga_block(fea):
    m = re.search(r"feature liga \{(.*?)\} liga;", fea, re.S)
    return m


def liga_map(font):
    rev = {}
    for g in font:
        for u in g.unicodes:
            rev.setdefault(g.name, u)
    out = {}
    m = liga_block(font.features.text)
    if not m:
        return out
    for comps, lig in LIGA_RE.findall(m.group(1)):
        comps = comps.split()
        if all(c in rev for c in comps):
            out["".join(chr(rev[c]) for c in comps)] = lig
    return out


def edit_features(font, keep_seqs):
    """Drop the source kern feature (replaced by ours) and ligatures the reference doesn't form."""
    fea = font.features.text
    fea = re.sub(r"\nfeature kern \{.*?\} kern;\n?", "\n", fea, flags=re.S)
    rev = {}
    for g in font:
        for u in g.unicodes:
            rev.setdefault(g.name, u)
    dropped = []
    m = liga_block(fea)
    if m:
        body = m.group(1)

        def repl(mm):
            comps = mm.group(1).split()
            if all(c in rev for c in comps):
                seq = "".join(chr(rev[c]) for c in comps)
                if seq not in keep_seqs:
                    dropped.append(seq)
                    return f"# {seq!r} not ligated (reference does not ligate it)"
            return mm.group(0)
        fea = fea[:m.start(1)] + LIGA_RE.sub(repl, body) + fea[m.end(1):]
    font.features.text = fea
    return dropped


def compress_kerning(pairs):
    """{(left, right): value} -> (groups, kerning) using UFO kern1/kern2 groups.

    Right-side groups gather glyphs with identical columns, left-side groups glyphs with
    identical rows (over right groups); the expansion equals the input exactly.
    """
    rows = collections.defaultdict(dict)
    for (a, b), v in pairs.items():
        rows[a][b] = v
    cols = collections.defaultdict(list)
    for a in sorted(rows):
        for b, v in sorted(rows[a].items()):
            cols[b].append((a, v))
    rsig = collections.defaultdict(list)
    for b, sig in cols.items():
        rsig[tuple(sig)].append(b)
    groups, rname = {}, {}
    for members in sorted(sorted(v) for v in rsig.values()):
        if len(members) == 1:
            rname[members[0]] = members[0]
        else:
            n = f"public.kern2.{members[0]}"
            groups[n] = members
            for b in members:
                rname[b] = n
    lsig = collections.defaultdict(list)
    for a, row in rows.items():
        lsig[tuple(sorted({(rname[b], v) for b, v in row.items()}))].append(a)
    kerning = {}
    for sig, members in lsig.items():
        members = sorted(members)
        if len(members) == 1:
            ln = members[0]
        else:
            ln = f"public.kern1.{members[0]}"
            groups[ln] = members
        for rn, v in sig:
            kerning[(ln, rn)] = v
    return groups, kerning


def transform_point(xf, x, y):
    sx, sy, dx, dy = xf
    return sx * x + dx, sy * y + dy


# ----------------------------------------------------------------------------- style build
def build_style(key, spaces, metrics_dir, out_dir, report):
    family, style, italic, weight, narrow, display, width_class = STYLES[key]
    ref = json.load(open(os.path.join(metrics_dir, f"ref_{key}.json")))
    vm = ref["vertical"]
    targets = {int(k): v for k, v in ref["advances"].items()}
    sp = spaces["italic" if italic else "roman"]
    s = vm["capHeight"] / SRC_CAP_HEIGHT
    assert vm["unitsPerEm"] == 2048

    W = BASE_WGHT[weight]
    target_stem = sp.stem(W, 100)
    grid = [(sp.wght_for_stem(target_stem, wd), wd, 1.0) for wd in WDTH_GRID]
    grid += [(sp.wght_for_stem(target_stem / k, max(WDTH_GRID)), max(WDTH_GRID), k) for k in STRETCH_WIDE]
    grid += [(sp.wght_for_stem(target_stem / k, min(WDTH_GRID)), min(WDTH_GRID), k) for k in STRETCH_NARROW]
    log(key, "scale %.5f" % s, "grid", grid)
    insts = {gw: sp.instance(gw[0], gw[1]) for gw in grid}
    any_inst = insts[grid[len(WDTH_GRID) - 1]]
    order = list(any_inst.lib.get("public.glyphOrder", [])) or list(any_inst.keys())
    order = [g for g in order if g in any_inst] + sorted(set(any_inst.keys()) - set(order))
    cmap = cmap_of(any_inst)

    # reference advance per glyph
    gtarget, gcp, conflicts = {}, {}, []
    for cp, g in sorted(cmap.items()):
        if cp in targets:
            if g in gtarget and gtarget[g] != targets[cp]:
                conflicts.append((cp, g, targets[cp], gtarget[g]))
                continue
            gtarget.setdefault(g, targets[cp])
            gcp.setdefault(g, cp)
    lig_targets = {}
    for seq, glyph in liga_map(any_inst).items():
        if seq in ref.get("ligatures", {}):
            gtarget[glyph] = ref["ligatures"][seq]
            lig_targets[seq] = (glyph, ref["ligatures"][seq])

    def is_composite(font, g):
        return not font[g].contours and bool(font[g].components)

    # 1. width-instance choice for simple encoded glyphs
    choice = {}
    for g, t in gtarget.items():
        if is_composite(any_inst, g):
            continue
        best = min(grid, key=lambda gw: (abs(t - insts[gw][g].width * s * gw[2]) / max(t, 1)
                                         + STRETCH_COST * abs(gw[2] - 1), abs(gw[1] - 100)))
        choice[g] = best
    lc = [choice[cmap[c]] for c in range(ord("a"), ord("z") + 1) if cmap.get(c) in choice]
    default_gw = collections.Counter(lc).most_common(1)[0][0]

    def base_of(g):
        if is_composite(any_inst, g):
            b = first_base(any_inst, g)
            if b != g:
                return b
        stem = g.split(".")[0]
        if stem != g and stem in any_inst:
            return stem
        if "_" in g and g.split("_")[0] in any_inst:
            return g.split("_")[0]
        if g in ("fi", "fl"):
            return "f"
        return None

    def resolve(g, depth=0):
        if g in choice:
            return choice[g]
        b = base_of(g)
        if b and depth < 8:
            return resolve(b, depth + 1)
        return default_gw

    # 2. per-glyph horizontal transform
    def box(font, g):
        bp = BoundsPen(font)
        font[g].draw(bp)
        return bp.bounds

    xform, rec, base_shift = {}, [], {}
    proc = sorted(order, key=lambda g: (is_composite(any_inst, g), g))
    for g in proc:
        gw = resolve(g)
        src = insts[gw][g]
        adv0 = src.width
        t = gtarget.get(g)
        b = base_of(g)
        k = gw[2]                               # composites inherit their base's gw (incl. stretch)
        sx = s * k
        n = adv0 * sx
        adv = t if t is not None else otround(n)
        D = adv - n
        bb = box(insts[gw], g)
        if bb is None:
            dx = D / 2 if adv0 else 0
        elif is_composite(any_inst, g) and b in base_shift:
            bD, bdx = base_shift[b]
            dx = bdx + (D - bD) / 2
        else:
            L, R = bb[0] * sx, n - bb[2] * sx
            dx = D * L / (L + R) if (L > 0 and R > 0) else D / 2
        sy, dy, shrink = s, 0.0, 1.0
        if bb is not None and t is not None and not is_composite(any_inst, g):
            # A symbol far wider than the reference advance would overlap its neighbours:
            # scale it down uniformly (about its vertical centre) instead. Letters are left alone.
            L0, R0 = bb[0] * sx, n - bb[2] * sx
            L1, R1 = L0 + dx, R0 + (D - dx)
            tol = 0.08 * t
            cat = unicodedata.category(chr(gcp[g]))[0] if g in gcp else "L"
            if cat in "SPN" and (L1 < min(0, L0) - tol or R1 < min(0, R0) - tol) and n > 0:
                shrink = adv / n
                sx, sy = sx * shrink, s * shrink
                n = adv0 * sx
                D = adv - n
                L, R = bb[0] * sx, n - bb[2] * sx
                dx = D * L / (L + R) if (L > 0 and R > 0) else D / 2
                cy = (bb[1] + bb[3]) / 2
                dy = cy * s - cy * sy
        if not is_composite(any_inst, g):
            base_shift[g] = (D, dx)
        xform[g] = (gw, (sx, sy, dx, dy), int(adv))
        if t is not None:
            rec.append(dict(glyph=g, cp=gcp.get(g), target=t, wdth=gw[1], wght=gw[0], stretch=round(k, 4),
                            shrink=round(shrink, 4), natural=round(adv0 * s, 1), sidebearing_total=round(D, 1),
                            rel=round(D / t, 4) if t else 0.0))

    # 3. assemble the style's UFO from the default-width instance
    font = copy.deepcopy(insts[default_gw])
    for g in order:
        gw, (sx, sy, dx, dy), adv = xform[g]
        src = insts[gw][g]
        dst = font[g]
        dst.clearContours()
        dst.clearComponents()
        dst.clearAnchors()
        dst.clearGuidelines()
        pen = dst.getPointPen()
        for c in src.contours:
            pen.beginPath()
            for p in c.points:
                x, y = transform_point((sx, sy, dx, dy), p.x, p.y)
                pen.addPoint((otround(x), otround(y)), p.type, p.smooth, p.name)
            pen.endPath()
        for c in src.components:
            xx, xy, yx, yy, ox, oy = c.transformation
            csx, csy, cdx, cdy = xform[c.baseGlyph][1]
            # T' = A_g . T . A_c^-1 with A = diag(sx, sy) + (dx, dy);
            # fontTools convention: x' = xx*x + yx*y + ox, y' = xy*x + yy*y + oy
            nxx, nyx = sx * xx / csx, sx * yx / csy
            nxy, nyy = sy * xy / csx, sy * yy / csy
            if abs(nxx - xx) < 0.05 and abs(nyy - yy) < 0.05 and abs(nxy - xy) < 0.02 and abs(nyx - yx) < 0.02:
                nxx, nxy, nyx, nyy = xx, xy, yx, yy
            nox = sx * ox + dx - (nxx * cdx + nyx * cdy)
            noy = sy * oy + dy - (nxy * cdx + nyy * cdy)
            pen.addComponent(c.baseGlyph, (nxx, nxy, nyx, nyy, otround(nox), otround(noy)))
        for a in src.anchors:
            x, y = transform_point((sx, sy, dx, dy), a.x, a.y)
            dst.appendAnchor({"name": a.name, "x": otround(x), "y": otround(y)})
        dst.width = adv
        dst.unicodes = list(src.unicodes)

    # 4. features: our kerning replaces the source's; ligatures as in the reference
    dropped = edit_features(font, set(ref.get("ligatures", {})))
    ligs_after = liga_map(font)
    pairs, unmapped = {}, 0
    # codepoint pairs first, so they win over ligature-sequence pairs mapping to the same glyphs
    for a, b, v in sorted(ref["kerning"], key=lambda r: not (isinstance(r[0], int) and isinstance(r[1], int))):
        ga = cmap.get(a) if isinstance(a, int) else ligs_after.get(a)
        gb = cmap.get(b) if isinstance(b, int) else ligs_after.get(b)
        if ga is None or gb is None:
            unmapped += 1
            continue
        pairs.setdefault((ga, gb), v)
    groups, kerning = compress_kerning(pairs)
    for gname in [n for n in font.groups if n.startswith(("public.kern1.", "public.kern2."))]:
        del font.groups[gname]
    font.groups.update(groups)
    font.kerning.clear()
    font.kerning.update(kerning)

    # 5. font info
    info = font.info
    sc = lambda v: otround(v * s) if v is not None else None
    info.familyName = family
    info.styleName = style
    info.styleMapFamilyName = family
    info.styleMapStyleName = style.lower()
    info.openTypeNamePreferredFamilyName = None
    info.openTypeNamePreferredSubfamilyName = None
    info.postscriptFontName = family.replace(" ", "") + "-" + style.replace(" ", "")
    info.postscriptFullName = f"{family} {style}"
    info.openTypeNameUniqueID = f"{VERSION[0]}.{VERSION[1]:03d};NONE;{info.postscriptFontName}"
    info.openTypeNameVersion = f"Version {VERSION[0]}.{VERSION[1]:03d}"
    info.versionMajor, info.versionMinor = VERSION
    info.copyright = COPYRIGHT
    info.trademark = None
    info.openTypeNameManufacturer = None
    info.openTypeNameManufacturerURL = None
    info.openTypeNameDesigner = "Steve Matteson (Open Sans); Apodi modifications by The Apodi Project Authors"
    info.openTypeNameDesignerURL = None
    info.openTypeNameDescription = DESCRIPTION
    info.openTypeNameLicense = LICENSE
    info.openTypeNameLicenseURL = "https://openfontlicense.org"
    info.openTypeNameRecords = []
    info.openTypeOS2VendorID = "NONE"
    info.unitsPerEm = vm["unitsPerEm"]
    info.ascender = vm["typoAscender"]
    info.descender = vm["typoDescender"]
    info.openTypeHheaAscender = vm["hheaAscender"]
    info.openTypeHheaDescender = vm["hheaDescender"]
    info.openTypeHheaLineGap = vm["hheaLineGap"]
    info.openTypeOS2TypoAscender = vm["typoAscender"]
    info.openTypeOS2TypoDescender = vm["typoDescender"]
    info.openTypeOS2TypoLineGap = vm["typoLineGap"]
    info.openTypeOS2WinAscent = vm["winAscent"]
    info.openTypeOS2WinDescent = vm["winDescent"]
    info.capHeight = otround(SRC_CAP_HEIGHT * s)
    info.xHeight = otround(box(font, "x")[3])
    info.italicAngle = vm["italicAngle"] or 0
    info.openTypeOS2WeightClass = vm["weightClass"]
    info.openTypeOS2WidthClass = width_class
    sel = [7] if vm.get("useTypoMetrics") else []
    info.openTypeOS2Selection = sel
    for attr in ("openTypeOS2SubscriptXSize", "openTypeOS2SubscriptYSize", "openTypeOS2SubscriptXOffset",
                 "openTypeOS2SubscriptYOffset", "openTypeOS2SuperscriptXSize", "openTypeOS2SuperscriptYSize",
                 "openTypeOS2SuperscriptXOffset", "openTypeOS2SuperscriptYOffset", "openTypeOS2StrikeoutSize",
                 "openTypeOS2StrikeoutPosition", "postscriptUnderlinePosition", "postscriptUnderlineThickness"):
        setattr(info, attr, sc(getattr(info, attr)))
    if info.openTypeOS2Panose:
        p = list(info.openTypeOS2Panose)
        p[2] = 8 if weight == "bold" else 5
        info.openTypeOS2Panose = p
    for attr in ("postscriptBlueValues", "postscriptOtherBlues", "postscriptFamilyBlues",
                 "postscriptFamilyOtherBlues", "postscriptStemSnapH", "postscriptStemSnapV"):
        setattr(info, attr, [])
    info.postscriptBlueScale = info.postscriptBlueShift = info.postscriptBlueFuzz = None
    info.postscriptForceBold = None
    info.guidelines = []
    info.openTypeGaspRangeRecords = [{"rangeMaxPPEM": 65535, "rangeGaspBehavior": [0, 1, 2, 3]}]
    info.openTypeHeadCreated = None
    info.note = ("Apodi: advance widths, vertical metrics and kerning are fitted for metric "
                 "compatibility. Changing an advance width or kerning value breaks it; see EDITING.md.")

    # 6. lib: drop source-editor noise, keep build-relevant keys, record fitted widths
    keep = {"public.glyphOrder", "public.postscriptNames", "public.skipExportGlyphs",
            "com.github.googlei18n.ufo2ft.filters", "public.openTypeCategories"}
    for k in list(font.lib):
        if k not in keep:
            del font.lib[k]
    font.lib["public.glyphOrder"] = order
    font.lib["org.apodi.lockedAdvanceWidths"] = {g: xform[g][2] for g in sorted(gtarget)}
    font.lib["org.apodi.fit"] = {
        "scale": s, "grid_wght_wdth_stretch": [list(g) for g in grid], "defaultInstance": list(default_gw),
        "mVertexRaise": M_VERTEX_RAISE, "defaultAlternates": DEFAULT_ALTERNATES["italic" if italic else "roman"],
    }
    for g in font:
        for k in list(g.lib):
            if k.startswith("com.schriftgestaltung") or k.startswith("com.typemytype"):
                del g.lib[k]
    for layer in list(font.layers):
        if layer is not font.layers.defaultLayer:
            font.layers.remove(layer.name)

    path = os.path.join(out_dir, f"{info.postscriptFontName}.ufo")
    if os.path.exists(path):
        shutil.rmtree(path)
    font.save(path)

    rels = [abs(r["rel"]) for r in rec]
    report[key] = dict(
        ufo=path, scale=s, grid=[list(g) for g in grid], default_instance=list(default_gw),
        glyphs_fitted=len(rec), conflicts=conflicts, ligature_targets=lig_targets, liga_dropped=dropped,
        kern_pairs=len(pairs), kern_pairs_unmapped=unmapped,
        kern_groups=len(groups), kern_entries=len(kerning),
        wdth_hist={str(k): v for k, v in sorted(collections.Counter(r["wdth"] for r in rec).items())},
        stretched=sum(1 for r in rec if r["stretch"] != 1),
        shrunk=[r["glyph"] for r in rec if r["shrink"] != 1],
        rel_sidebearing=dict(median=statistics.median(rels), p90=sorted(rels)[int(0.9 * len(rels))],
                             max=max(rels), over_2pct=sum(r > 0.02 for r in rels),
                             over_5pct=sum(r > 0.05 for r in rels), over_10pct=sum(r > 0.10 for r in rels)),
        worst=sorted(rec, key=lambda r: -abs(r["rel"]))[:20],
        per_glyph=rec,
    )
    report.setdefault("_glyphset", set()).update(gtarget)
    log(key, "->", path, "kern pairs", len(pairs), "groups", len(groups), "entries", len(kerning))
    return info.postscriptFontName


def write_designspace(out_dir, built):
    """Masters on wght/wdth/opsz axes plus a discrete ital axis; one instance per master."""
    ds = DesignSpaceDocument()
    ds.formatVersion = "5.0"
    for tag, name, mn, df, mx in (("wght", "Weight", 400, 400, 700), ("wdth", "Width", 87.5, 100, 100),
                                  ("opsz", "Optical size", 11, 11, 24)):
        a = AxisDescriptor()
        a.tag, a.name, a.minimum, a.default, a.maximum = tag, name, mn, df, mx
        ds.addAxis(a)
    ital = DiscreteAxisDescriptor()
    ital.tag, ital.name, ital.values, ital.default = "ital", "Italic", [0, 1], 0
    ds.addAxis(ital)
    for key, ps in built.items():
        family, style, italic, weight, narrow, display, _ = STYLES[key]
        loc = {"Weight": 700 if weight == "bold" else 400, "Width": 87.5 if narrow else 100,
               "Optical size": 24 if display else 11, "Italic": 1 if italic else 0}
        src = SourceDescriptor()
        src.filename = f"{ps}.ufo"
        src.familyName, src.styleName, src.name = family, style, ps
        src.location = loc
        ds.addSource(src)
        ins = InstanceDescriptor()
        ins.familyName, ins.styleName = family, style
        ins.styleMapFamilyName, ins.styleMapStyleName = family, style.lower()
        ins.postScriptFontName = ps
        ins.filename = f"{ps}.ufo"
        ins.location = loc
        ds.addInstance(ins)
    ds.lib["org.apodi.note"] = (
        "Each source is a complete static style (built as-is by fontmake -u / -m ... -o ttf). The "
        "sources share Open Sans's point structure, but advance widths are fitted per glyph, so "
        "interpolating between them is not a designed intermediate style.")
    ds.write(os.path.join(out_dir, "Apodi.designspace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opensans", required=True, help="Open Sans sources/ directory")
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--styles", default=",".join(STYLES))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    spaces = {}
    log("loading Open Sans designspaces")
    spaces["roman"] = OpenSansSpace(os.path.join(a.opensans, "OpenSans-Roman.designspace"),
                                    DEFAULT_ALTERNATES["roman"])
    spaces["italic"] = OpenSansSpace(os.path.join(a.opensans, "OpenSans-Italic.designspace"),
                                     DEFAULT_ALTERNATES["italic"])
    report, built = {}, {}
    for k in a.styles.split(","):
        built[k] = build_style(k, spaces, a.metrics, a.out, report)
    if set(built) == set(STYLES):
        write_designspace(a.out, built)
    # shipped glyph set: Open Sans's own shipped set + every glyph the reference metrics cover
    upstream = open(os.path.join(a.opensans, "OpenSans-glyphset.txt")).read().split()
    # the upstream list mixes UFO names and production names (e.g. uni05D0 for alef-hb)
    nice = {v: k for k, v in spaces["roman"].ds.sources[0].font.lib.get("public.postscriptNames", {}).items()}
    nice.update({v: k for k, v in spaces["italic"].ds.sources[0].font.lib.get("public.postscriptNames", {}).items()})
    upstream = [nice.get(n, n) for n in upstream]
    shipped = sorted(set(upstream) | report.pop("_glyphset"))
    with open(os.path.join(a.out, "glyphset.txt"), "w") as fh:
        fh.write("# Glyphs shipped in the Apodi binaries (UFO glyph names); the build subsets to these\n"
                 "# plus whatever they reach through components and OpenType features.\n")
        fh.write("\n".join(shipped) + "\n")
    # drop glyphs that don't ship (and their feature rules) from the UFOs
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from prune import closure, prune_fea, prune_ufo
    for italic in (False, True):
        keys = [k for k in built if STYLES[k][2] == italic]
        if not keys:
            continue
        paths = [os.path.join(a.out, f"{built[k]}.ufo") for k in keys]
        keep = closure(ufoLib2.Font.open(paths[0]), shipped)
        for p in paths:
            ufo = ufoLib2.Font.open(p)
            ufo.features.text = prune_fea(ufo.features.text, keep, list(ufo.keys()))
            prune_ufo(ufo, keep)
            ufo.save(p, overwrite=True)
        log("pruned", "italic" if italic else "roman", "to", len(keep), "glyphs")
    with open(a.report or os.path.join(a.out, "..", "fit_report.json"), "w") as fh:
        json.dump(report, fh, indent=1)


if __name__ == "__main__":
    main()
