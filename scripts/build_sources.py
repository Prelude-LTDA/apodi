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
  4. design changes on each instance (before 1-3): raises the M's middle vertex, draws G, K and k
     with Open Sans's Cyrillic Komi Sje, Ka and ka, cuts C c S s out of O o 8, and in the italics
     replaces e f c C s S (and the f ligatures) with the matching roman glyphs slanted;
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
M_VERTEX_RAISE = 0.25                           # M middle vertex raised by 25% of cap height
# Latin letters drawn with Open Sans's own Cyrillic outline (same space: upright from the roman,
# slanted from the italic): G takes Komi Sje (U+050C), K takes Ka (U+041A). Names, Unicode values,
# kerning and groups stay the Latin glyph's.
CYRILLIC_OUTLINES = {"G": "uni050C", "K": "afii10028"}
# Lowercase k is Cyrillic ka (U+043A) with its stem extended up to k's ascender.
K_CYRILLIC_LC = 0x043A
# C and c are cut out of O and o: a rectangle covering the right side of the bowl (fractions of
# the source glyph's bounding box: x from CUT_C[0] to beyond the right edge, y from CUT_C[1]
# to CUT_C[2]) is removed, which leaves flat horizontal terminals.
CUT_C = {"C": ("O", 0.50, 0.30, 0.70), "c": ("o", 0.50, 0.30, 0.70)}
# S and s are cut out of 8: the upper-right quadrant (from the centre to the right edge, from
# the waist to CUT_S[1] of the height) and the lower-left quadrant (from the left edge to the
# centre, from CUT_S[0] up to the waist) are removed, and the 8's waist is replaced by a drawn
# spine (S_SPINE; see cut_S_from_8). s uses the 8 scaled to x-height, drawn at the weight that
# gives s's own horizontal stroke and o's stem after scaling.
CUT_S = {"S": (0.29, 0.72), "s": (0.32, 0.69)}
# The S/s spine (see cut_S_from_8): angle from the horizontal at the centre (degrees), weight as
# a multiple of the bowls' vertical strokes, and where it joins the bowls (fraction of each
# counter's height, from the waist).
S_SPINE = {"S": (33.0, 1.0, 0.5), "s": (29.5, 1.0, 0.5)}
# In the italics these glyphs are the matching roman's (same wdth, weight and stretch) slanted
# by the italic angle: obliques, instead of Open Sans's cursive forms. The f ligatures follow f.
OBLIQUE_ITALIC = ["e", "eogonek", "eogonek.loclNAV", "f", "c", "C", "s", "S", "f_f", "fi", "fl", "f_f_i", "f_f_l"]
VERSION = (1, 2)

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

    def __init__(self, ds_path, swaps=(), roman=True):
        self.swaps = swaps
        self.roman = roman
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
            apply_outline_changes(f, self, (wght, wdth), self.roman)
            self._cache[key] = f
        return self._cache[key]

    def glyph(self, name, wght, wdth):
        """One glyph interpolated at (wght, wdth), without building the whole instance."""
        loc = self.inst.normalize({self.axes["wght"].name: self.axes["wght"].map_forward(wght),
                                   self.axes["wdth"].name: self.axes["wdth"].map_forward(wdth)})
        return self.inst.generate_glyph_instance(name, loc)

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


# ----------------------------------------------------------------------------- design changes: outlines
# Each change redraws a glyph inside one interpolated Open Sans instance, before fitting, so the
# width choice and the locked advance work on the new drawing like on any other glyph.
# Composites built on a redrawn glyph keep their width relation to it, and their marks move
# with the base's anchors.

def contours_of(glyph):
    """[(points)], points = (x, y, type, smooth) - a plain copy of a glyph's contours."""
    return [[(p.x, p.y, p.type, p.smooth) for p in c.points] for c in glyph.contours]


def bounds_of(contours):
    bp = BoundsPen(None)
    draw_contours(contours, bp)
    return bp.bounds


def draw_contours(contours, pen):
    from fontTools.pens.pointPen import PointToSegmentPen
    ppen = pen if hasattr(pen, "addPoint") else PointToSegmentPen(pen)
    for c in contours:
        ppen.beginPath()
        for x, y, t, sm in c:
            ppen.addPoint((x, y), t, sm)
        ppen.endPath()


def signed_area(contours):
    from fontTools.pens.areaPen import AreaPen
    ap = AreaPen()
    draw_contours(contours, ap)
    return ap.value


def to_path(contours):
    import pathops
    path = pathops.Path()
    draw_contours(contours, path.getPen())
    return path


def from_path(path):
    """pathops.Path -> contours, outer contours counter-clockwise (PostScript direction, as in
    Open Sans's UFOs)."""
    from fontTools.pens.recordingPen import RecordingPointPen
    from fontTools.pens.pointPen import SegmentToPointPen
    rec = RecordingPointPen()
    path.draw(SegmentToPointPen(rec))
    out, cur = [], None
    for op, args, kw in rec.value:
        if op == "beginPath":
            cur = []
        elif op == "addPoint":
            (x, y), t = args[0], args[1] if len(args) > 1 else kw.get("segmentType")
            cur.append((x, y, t, False))
        elif op == "endPath":
            out.append(cur)
    out = [mark_smooth(drop_degenerate(c)) for c in out]
    if signed_area(out) < 0:
        out = [reverse_contour(c) for c in out]
    return out


def drop_degenerate(c, eps=1.0):
    """Remove zero-length segments (a boolean can leave a curve whose points all coincide)."""
    on = [i for i, p in enumerate(c) if p[2] is not None]
    if len(on) < 3:
        return c
    segs = []                                   # (off-curves, on-curve) ending at each on-curve
    n = len(c)
    for k, i in enumerate(on):
        j = on[k - 1]
        offs = [c[m % n] for m in range(j + 1, i + (n if i <= j else 0))]
        segs.append((offs, c[i]))
    keep = []
    for k, (offs, p) in enumerate(segs):
        prev = segs[k - 1][1]
        if all(math.hypot(q[0] - prev[0], q[1] - prev[1]) < eps for q in offs + [p]) and len(segs) - k + len(keep) > 2:
            continue
        keep.append((offs, p))
    out = []
    for offs, p in keep:
        out.extend(offs)
        out.append(p)
    return out


def reverse_contour(c):
    from fontTools.pens.recordingPen import RecordingPointPen
    from fontTools.pens.reverseContourPointPen import ReverseContourPointPen
    rec = RecordingPointPen()
    draw_contours([c], ReverseContourPointPen(rec))
    return [(a[0][0], a[0][1], a[1] if len(a) > 1 else k.get("segmentType"), k.get("smooth", False))
            for op, a, k in rec.value if op == "addPoint"]


def mark_smooth(c, tol_deg=4.0):
    """Flag on-curve points whose in and out tangents are collinear (within tol) as smooth."""
    n, out = len(c), []
    for i, (x, y, t, sm) in enumerate(c):
        if t is not None:
            px, py = c[i - 1][:2]
            nx, ny = c[(i + 1) % n][:2]
            a1, a2 = math.atan2(y - py, x - px), math.atan2(ny - y, nx - x)
            d = abs((math.degrees(a2 - a1) + 180) % 360 - 180)
            sm = (px, py) != (x, y) and (nx, ny) != (x, y) and d < tol_deg
        out.append((x, y, t, sm))
    return out


def polygon(pts):
    return [[(x, y, "line", False) for x, y in pts]]


def difference(contours, cutters):
    import pathops
    res = to_path(contours)
    for cut in cutters:
        res = pathops.op(res, to_path(cut), pathops.PathOp.DIFFERENCE, fix_winding=True)
    return from_path(res)


def flatten(contours, steps=24):
    """Contours as closed polylines (for measuring stroke thickness)."""
    polys = []
    for c in contours:
        on = [i for i, p in enumerate(c) if p[2] is not None]
        if not on:
            continue
        n, poly = len(c), []
        start = on[0]
        i = start
        while True:
            j = (i + 1) % n
            offs = []
            while c[j][2] is None:
                offs.append(c[j][:2])
                j = (j + 1) % n
            p0, p3 = c[i][:2], c[j][:2]
            if len(offs) == 2:
                for k in range(1, steps + 1):
                    t = k / steps
                    mt = 1 - t
                    poly.append(tuple(mt ** 3 * a + 3 * mt * mt * t * b + 3 * mt * t * t * cc + t ** 3 * d
                                      for a, b, cc, d in zip(p0, offs[0], offs[1], p3)))
            else:
                poly.append(p3)
            i = j
            if i == start:
                break
        polys.append(poly)
    return polys


def crossings(contours, y=None, x=None):
    """Sorted crossing coordinates of a horizontal (y=...) or vertical (x=...) line."""
    out = []
    for poly in flatten(contours):
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if y is not None and (y0 - y) * (y1 - y) < 0:
                out.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            if x is not None and (x0 - x) * (x1 - x) < 0:
                out.append(y0 + (x - x0) * (y1 - y0) / (x1 - x0))
    return sorted(out)


def set_drawing(font, name, contours, anchors, width, components=()):
    """Redraw `name` in `font`. Composites built on it keep their width relation to it, and their
    mark components move with the base anchor they attach to."""
    g = font[name]
    old_anchors = {a.name: (a.x, a.y) for a in g.anchors}
    old_width = g.width
    g.clearContours()
    g.clearComponents()
    g.clearAnchors()
    pen = g.getPointPen()
    for c in contours:
        pen.beginPath()
        for x, y, t, sm in c:
            pen.addPoint((otround(x), otround(y)), t, sm)
        pen.endPath()
    for base, xf in components:
        pen.addComponent(base, xf)
    for an, (x, y) in anchors.items():
        g.appendAnchor({"name": an, "x": otround(x), "y": otround(y)})
    g.width = otround(width)
    new_anchors = {an: (otround(x), otround(y)) for an, (x, y) in anchors.items()}
    def delta(an):
        return (new_anchors[an][0] - old_anchors[an][0], new_anchors[an][1] - old_anchors[an][1])
    has = [an for an in old_anchors if an in new_anchors]
    mid = (old_anchors.get("top", (0, 1000))[1] + old_anchors.get("bottom", (0, 0))[1]) / 2

    def side(y):
        # attachments with no matching anchor (e.g. an ogonek drawn into the composite) move with
        # the base's bottom or top anchor, whichever side of the base they sit on
        an = "top" if y > mid else "bottom"
        return delta(an) if an in has else (0, 0)
    for cg in font:
        if not cg.components or cg.components[0].baseGlyph != name:
            continue
        if tuple(cg.components[0].transformation)[:4] != (1, 0, 0, 1):
            continue
        if cg.width > 0:
            cg.width = g.width + (cg.width - old_width)
        for comp in cg.components[1:]:
            mark = font[comp.baseGlyph] if comp.baseGlyph in font else None
            names = [a.name[1:] for a in (mark.anchors if mark else []) if a.name.startswith("_")]
            names = [an for an in names if an in has]
            if names:
                ddx, ddy = delta(names[0])
            else:
                mb = glyph_bounds(font, comp.baseGlyph) if mark is not None else None
                if mb is None:
                    continue
                ddx, ddy = side((mb[1] + mb[3]) / 2 + comp.transformation[5])
            t = list(comp.transformation)
            t[4] += ddx
            t[5] += ddy
            comp.transformation = tuple(t)
        for c in cg.contours:
            ys = [p.y for p in c.points]
            ddx, ddy = side((min(ys) + max(ys)) / 2)
            for p in c.points:
                p.x += ddx
                p.y += ddy
        for a in cg.anchors:
            ddx, ddy = delta(a.name) if a.name in has else side(a.y)
            a.x += ddx
            a.y += ddy


def fit_anchors(orig_glyph, orig_bounds, new_bounds, source_anchors=None):
    """Anchors for a redrawn glyph, with the original glyph's anchor names. A name the source
    drawing has takes the source's position; `topright` keeps its distance from the right edge;
    any other keeps its offset from the centre of the bounding box."""
    out = {}
    src = source_anchors or {}
    oc = (orig_bounds[0] + orig_bounds[2]) / 2
    nc = (new_bounds[0] + new_bounds[2]) / 2
    for a in orig_glyph.anchors:
        if a.name == "topright":
            out[a.name] = (new_bounds[2] + (a.x - orig_bounds[2]), a.y)
        elif a.name in src:
            out[a.name] = src[a.name]
        else:
            out[a.name] = (nc + (a.x - oc), a.y)
    return out


def use_outline(font, name, source):
    """Draw `name` with `source`'s outline (e.g. Latin G with Cyrillic Komi Sje)."""
    g, s = font[name], font[source]
    assert s.contours and not s.components, (source, "is not a simple glyph")
    cs = contours_of(s)
    anchors = fit_anchors(g, glyph_bounds(font, name), bounds_of(cs), {a.name: (a.x, a.y) for a in s.anchors})
    set_drawing(font, name, cs, anchors, s.width)


def k_from_cyrillic(font):
    """Lowercase k drawn with Cyrillic ka (U+043A): its stem is extended from the x-height to
    the Latin k's ascender (along the slant in italics); the stem top stays flat, as on l and h."""
    ka = next(g.name for g in font if K_CYRILLIC_LC in g.unicodes)
    src = font[ka]
    assert src.contours and not src.components, (ka, "is not a simple glyph")
    cs = contours_of(src)
    top = max(p[1] for c in cs for p in c if p[2] is not None)
    stem_top = sorted(((ci, pi) for ci, c in enumerate(cs) for pi, p in enumerate(c)
                       if p[2] is not None and abs(p[1] - top) < 1), key=lambda t: cs[t[0]][t[1]][0])[:2]
    assert len(stem_top) == 2, "unexpected ka structure"
    kb = glyph_bounds(font, "k")
    dy = kb[3] - top
    dx = -math.tan(math.radians(font.info.italicAngle or 0)) * dy
    for ci, pi in stem_top:
        x, y, t, sm = cs[ci][pi]
        cs[ci][pi] = (x + dx, y + dy, t, sm)
    src_anchors = {a.name: (a.x, a.y) for a in src.anchors if a.name == "bottom"}
    anchors = fit_anchors(font["k"], kb, bounds_of(cs), src_anchors)
    set_drawing(font, "k", cs, anchors, src.width)


def glyph_bounds(font, name):
    bp = BoundsPen(font)
    font[name].draw(bp)
    return bp.bounds


def cut_C_from_O(font, name):
    src, fx, ylo, yhi = CUT_C[name]
    cs = contours_of(font[src])
    x0, y0, x1, y1 = bounds_of(cs)
    w, h = x1 - x0, y1 - y0
    rect = polygon([(x0 + fx * w, y0 + ylo * h), (x1 + w, y0 + ylo * h),
                    (x1 + w, y0 + yhi * h), (x0 + fx * w, y0 + yhi * h)])
    new = difference(cs, [rect])
    nb = bounds_of(new)
    anchors = fit_anchors(font[name], glyph_bounds(font, name), nb,
                          {a.name: (a.x, a.y) for a in font[src].anchors if a.name != "topright"})
    # the right sidebearing of O carries over; the cut only removes ink
    set_drawing(font, name, new, anchors, font[src].width)


def eight_parts(cs):
    """The 8's outer contour and two counters, and the points where its waist is drawn, each with
    the direction in which the S's spine edge leaves or enters it: the outer contour's left and
    right corners at the waist (AL, AR), the upper counter's bottom corner (U) and the lower
    counter's top corner (LW)."""
    assert len(cs) == 3, "unexpected 8 structure"
    by_size = sorted(cs, key=lambda c: -abs(signed_area([c])))
    outer, counters = by_size[0], by_size[1:]
    upper, lower = sorted(counters, key=lambda c: -sum(p[1] for p in c) / len(c))

    def corners(c):
        return [i for i, p in enumerate(c) if p[2] is not None and not p[3]]

    def nbrs(c, i):
        return c[i - 1][:2], c[(i + 1) % len(c)][:2]

    def unit(dx, dy):
        n = math.hypot(dx, dy)
        return dx / n, dy / n
    oc = corners(outer)
    assert len(oc) == 2, ("unexpected 8 waist", oc)
    iL, iR = sorted(oc, key=lambda i: outer[i][0])
    iU = min(corners(upper), key=lambda i: upper[i][1])
    iW = max(corners(lower), key=lambda i: lower[i][1])
    aL, aR, u, lw = outer[iL][:2], outer[iR][:2], upper[iU][:2], lower[iW][:2]
    # spine edges run left to right: tangent of the upper counter's left arc at U, of the outer
    # contour's lower-right bowl at AR, of its upper-left bowl at AL, and of the lower counter's
    # right arc at LW
    n = max(nbrs(upper, iU), key=lambda q: -q[0])
    dU = unit(u[0] - n[0], u[1] - n[1])
    n = min(nbrs(outer, iR), key=lambda q: q[1])
    dR = unit(n[0] - aR[0], n[1] - aR[1])
    n = max(nbrs(outer, iL), key=lambda q: q[1])
    dL = unit(aL[0] - n[0], aL[1] - n[1])
    n = max(nbrs(lower, iW), key=lambda q: q[0])
    dW = unit(n[0] - lw[0], n[1] - lw[1])
    return outer, upper, lower, (aL, dL), (aR, dR), (u, dU), (lw, dW)


def edge_at(contour, y, pick):
    """The point where a contour crosses the height y (pick=min: leftmost crossing, max:
    rightmost) and the contour's unit direction there, oriented to point down."""
    hits = []
    for poly in flatten([contour], steps=64):
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 - y) * (y1 - y) < 0:
                x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                dx, dy = (x1 - x0, y1 - y0) if y1 < y0 else (x0 - x1, y0 - y1)
                n = math.hypot(dx, dy)
                hits.append((x, (dx / n, dy / n)))
    x, d = pick(hits, key=lambda h: h[0])
    return (x, y), d


def cut_S_from_8(cs, ylo, yhi, spine):
    """S out of an 8: its upper-right and lower-left quarters are cut away (the terminals end in
    flat horizontal cuts at yhi / ylo of the height) and the waist is replaced by a drawn spine.

    The spine is a band whose two edges are single cubics: they leave the top bowl's left stroke
    and join the bottom bowl's right stroke tangentially, at `join` of each counter's height
    from the waist; their handle lengths give them `angle` degrees from the horizontal half-way
    and set the spine's thickness there (perpendicular) to `weight` x the bowls' vertical
    strokes. The 8 is cut along the same curves and the band is added (union), so no stub of the
    8's other diagonal remains, the 8's pointed counters become round, and the bowls run into
    the spine without corners. The cuts' vertical sides pass through the counters only.
    """
    angle, weight, join = spine
    outer, upper, lower = eight_parts(cs)[:3]
    x0, y0, x1, y1 = bounds_of(cs)
    h = y1 - y0
    yT, yB = y0 + yhi * h, y0 + ylo * h
    ub, lb = bounds_of([upper]), bounds_of([lower])
    assert ub[1] < yT < ub[3] and lb[1] < yB < lb[3], "S cut heights outside the 8's counters"
    yL = ub[1] + join * (ub[3] - ub[1])
    yR = lb[3] - join * (lb[3] - lb[1])
    pu, du = edge_at(upper, yL, min)            # spine's upper edge leaves the upper counter
    pl, dl = edge_at(outer, yL, min)            # lower edge leaves the outer contour
    qu, eu = edge_at(outer, yR, max)            # upper edge joins the outer contour
    ql, el = edge_at(lower, yR, max)            # lower edge joins the lower counter
    a = math.radians(angle)
    tm = (math.cos(a), -math.sin(a))            # spine direction at its middle, down to the right
    nm = (math.sin(a), math.cos(a))             # its normal, up
    stem = (stem_v([outer, upper], (ub[1] + ub[3]) / 2) + stem_v([outer, lower], (lb[1] + lb[3]) / 2)) / 2
    cr = lambda u, v: u[0] * v[1] - u[1] * v[0]

    def base_k(p, dp, q, dq):
        # equal handles giving the curve the direction tm half-way:
        # B'(1/2) = 1.5 (q - p) - 0.75 (k1 dp + k2 dq), parallel to tm
        D = (q[0] - p[0], q[1] - p[1])
        S = (dp[0] + dq[0], dp[1] + dq[1])
        return 1.5 * cr(D, tm) / (0.75 * cr(S, tm)), math.hypot(*D)

    def mid(p, dp, q, dq, k1, k2):
        return ((p[0] + q[0]) / 2 + 0.375 * (k1 * dp[0] - k2 * dq[0]),
                (p[1] + q[1]) / 2 + 0.375 * (k1 * dp[1] - k2 * dq[1]))
    ku, Lu = base_k(pu, du, qu, eu)
    kl, Ll = base_k(pl, dl, ql, el)
    # unequal handles move each edge's middle across the spine without turning it: the upper
    # edge by +d / -d, the lower by -d / +d, with d giving the spine `weight` x the bowls' stroke

    def thickness(d):
        mu = mid(pu, du, qu, eu, ku + d, ku - d)
        ml = mid(pl, dl, ql, el, kl - d, kl + d)
        return (mu[0] - ml[0]) * nm[0] + (mu[1] - ml[1]) * nm[1]
    t0, t1 = thickness(0.0), thickness(1.0)
    d = (weight * stem - t0) / (t1 - t0) if abs(t1 - t0) > 1e-9 else 0.0

    def curve(p, dp, q, dq, k1, k2, L):
        k1, k2 = (min(max(k, 0.15 * L), 1.2 * L) for k in (k1, k2))
        return [(p[0] + dp[0] * k1, p[1] + dp[1] * k1, None, False),
                (q[0] - dq[0] * k2, q[1] - dq[1] * k2, None, False), (*q, "curve", False)]
    up = curve(pu, du, qu, eu, ku + d, ku - d, Lu)     # from pu to qu
    lo = curve(pl, dl, ql, el, kl - d, kl + d, Ll)     # from pl to ql
    m = 20
    cut_ur = [[(*pu, "line", False)] + up + [(x1 + m, qu[1], "line", False), (x1 + m, yT, "line", False),
                                             (pu[0], yT, "line", False)]]
    cut_ll = [[(*pl, "line", False)] + lo + [(ql[0], yB, "line", False), (x0 - m, yB, "line", False),
                                             (x0 - m, pl[1], "line", False)]]
    c1, c2, _ = lo
    back = [(*ql, "line", False), c2, c1, (*pl, "curve", False)]
    band = [[(*pu, "line", False)] + up[:-1] + [(*qu, "curve", False)] + back]
    import pathops
    res = to_path(cs)
    for cut in (cut_ur, cut_ll):
        res = pathops.op(res, to_path(cut), pathops.PathOp.DIFFERENCE, fix_winding=True)
    res = pathops.op(res, to_path(band), pathops.PathOp.UNION, fix_winding=True)
    return from_path(res)


def stroke_h(cs):
    """Thickness of the top horizontal stroke, at the centre of the bounding box."""
    x0, y0, x1, y1 = bounds_of(cs)
    ys = crossings(cs, x=(x0 + x1) / 2)
    return ys[-1] - ys[-2]


def stem_v(cs, y):
    """Thickness of the leftmost vertical stroke at height y."""
    xs = crossings(cs, y=y)
    return xs[1] - xs[0]


def make_S(font, name, space=None, location=None):
    if name == "S":
        cs = contours_of(font["eight"])
    else:
        cs = small_eight(font, space, location)
    new = cut_S_from_8(cs, *CUT_S[name], S_SPINE[name])
    nb = bounds_of(new)
    anchors = fit_anchors(font[name], glyph_bounds(font, name), nb)
    # sidebearings: the original S's (the 8 is a tabular figure with wide ones)
    ob = glyph_bounds(font, name)
    lsb, rsb = ob[0], font[name].width - ob[2]
    dx = lsb - nb[0]
    new = [[(x + dx, y, t, sm) for x, y, t, sm in c] for c in new]
    anchors = {k: (x + dx, y) for k, (x, y) in anchors.items()}
    set_drawing(font, name, new, anchors, lsb + (nb[2] - nb[0]) + rsb)


def small_eight(font, space, location):
    """An x-height 8 for s: Open Sans's 8 interpolated at the weight where, scaled down to the
    height of o, its top stroke is as thick as s's and then narrowed so its bowls' sides are as
    thick as o's stem."""
    wght, wdth = location
    s_cs, o_cs = contours_of(font["s"]), contours_of(font["o"])
    target_h = stroke_h(s_cs)
    ob = bounds_of(o_cs)
    target_v = stem_v(o_cs, (ob[1] + ob[3]) / 2)

    def eight_at(w):
        return contours_of(space.glyph("eight", min(w, 800.0), wdth))

    def scaled_h(w):
        e = eight_at(w)
        eb = bounds_of(e)
        return stroke_h(e) * (ob[3] - ob[1]) / (eb[3] - eb[1])
    lo, hi = wght, 800.0
    if scaled_h(hi) < target_h:
        lo = hi
    else:
        for _ in range(12):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if scaled_h(mid) < target_h else (lo, mid)
    e = eight_at(lo)
    eb = bounds_of(e)
    sy = (ob[3] - ob[1]) / (eb[3] - eb[1])
    lower = eight_parts(e)[2]
    lb = bounds_of([lower])
    sx = target_v / stem_v(e, (lb[1] + lb[3]) / 2)
    return [[(eb[0] + (x - eb[0]) * sx, ob[1] + (y - eb[1]) * sy, t, sm) for x, y, t, sm in c] for c in e]


def apply_outline_changes(font, space=None, location=None, roman=True):
    """Design changes made on every Open Sans instance before fitting (see the parameters at the
    top): G and K from the Cyrillic drawings; in the roman, C c S s cut out of O o 8."""
    for latin, cyr in CYRILLIC_OUTLINES.items():
        use_outline(font, latin, cyr)
    k_from_cyrillic(font)
    if roman:
        for name in CUT_C:
            cut_C_from_O(font, name)
        make_S(font, "s", space, location)       # before S: measures the instance's own s
        make_S(font, "S")


def skew_glyph_into(dst_font, src_font, name, t, y0):
    """dst[name] := src[name] slanted: x' = x + t (y - y0). Components keep their base glyph
    (which is slanted the same way when it is in OBLIQUE_ITALIC) with the offset slanted."""
    g = src_font[name]
    cs = [[(x + t * (y - y0), y, tp, sm) for x, y, tp, sm in c] for c in contours_of(g)]
    comps = []
    for c in g.components:
        xx, xy, yx, yy, ox, oy = c.transformation
        comps.append((c.baseGlyph, (xx, xy, yx, yy, otround(ox + t * oy), oy)))
    anchors = {a.name: (a.x + t * (a.y - y0), a.y) for a in g.anchors}
    old = {a.name for a in dst_font[name].anchors}
    for a in dst_font[name].anchors:              # names the roman lacks keep the italic's
        if a.name not in anchors:
            anchors[a.name] = (a.x, a.y)
    del old
    set_drawing(dst_font, name, cs, anchors, g.width, comps)


def apply_obliques(italic_font, roman_font):
    """Italic e f c C s S (and the f ligatures): the roman drawings, slanted by the italic angle
    about half the x-height."""
    angle = italic_font.info.italicAngle or 0
    t = math.tan(math.radians(-angle))
    y0 = roman_font.info.xHeight / 2
    for name in OBLIQUE_ITALIC:
        if name in italic_font and name in roman_font:
            skew_glyph_into(italic_font, roman_font, name, t, y0)


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
    if italic:
        # obliques: each italic instance takes its glyphs from the roman instance the matching
        # upright style uses at the same wdth and stretch (stem solved the same way)
        rsp = spaces["roman"]
        r_stem = rsp.stem(W, 100)
        for gw in grid:
            wr = rsp.wght_for_stem(r_stem / gw[2], gw[1])
            f = insts[gw]
            tag = [wr, gw[1]]
            prev = f.lib.get("org.apodi.obliqueFrom")
            if prev == tag:
                continue
            assert prev is None, ("italic instance shared by two roman matches", gw, prev, tag)
            apply_obliques(f, rsp.instance(wr, gw[1]))
            f.lib["org.apodi.obliqueFrom"] = tag
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
        "cyrillicOutlines": CYRILLIC_OUTLINES, "kFromCyrillic": "U+%04X" % K_CYRILLIC_LC,
        "sSpine": {k: list(v) for k, v in S_SPINE.items()}, "cutC": {k: list(v) for k, v in CUT_C.items()},
        "cutS": {k: list(v) for k, v in CUT_S.items()}, "obliques": OBLIQUE_ITALIC if italic else [],
    }
    for g in font:
        for k in list(g.lib):
            if k.startswith("com.schriftgestaltung") or k.startswith("com.typemytype"):
                del g.lib[k]
    for layer in list(font.layers):
        if layer is not font.layers.defaultLayer:
            font.layers.remove(layer.name)

    path = os.path.join(out_dir, f"{info.postscriptFontName}.ufo")
    for _ in range(5):                          # a file manager may drop .DS_Store meanwhile
        if not os.path.exists(path):
            break
        shutil.rmtree(path, ignore_errors=True)
    font.save(path, overwrite=True)

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
                                     DEFAULT_ALTERNATES["italic"], roman=False)
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
