"""Characters Open Sans lacks, drawn from Noto fonts (SIL OFL 1.1, no Reserved Font Name) and
fitted into an Apodi style like the Open Sans glyphs: scaled to Apodi's size, at the style's
stem weight, at the reference's advance width.

The fonts come from google/fonts at a pinned commit (scripts/fetch_noto.sh -> .noto/). Called by
build_sources.py for every style; nothing here reads the reference fonts except the numbers in
the ref_<Style>.json files (advance widths, and the bounding boxes of the box-drawing and
integral-piece characters, which must join across lines and neighbours).
"""
import ctypes
import math
import os
import unicodedata

import freetype
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

NOTO_EM_CAP = 714 / 1000            # cap height of the Noto Sans family, per em (same as Open Sans)

# codepoints -> (font file, how its weight is matched)
#   "vf"     variable font: interpolated at the wght (and wdth) that gives the style's stem
#   "static" one Regular master: emboldened / condensed with FreeType's outline emboldening
#   "fill"   one Regular master, a filled shape: scaled only
SOURCES = {}


def _src(cps, font, kind):
    for cp in cps:
        SOURCES[cp] = (font, kind)


_src(range(0x03E2, 0x03F0), "NotoSansCoptic-Regular.ttf", "static")
_src([0x058F], "NotoSansArmenian[wdth,wght].ttf", "vf")
_src([0x060B, 0xFDFC], "NotoSansArabic[wdth,wght].ttf", "vf")
_src([0x09F2, 0x09F3], "NotoSansBengali[wdth,wght].ttf", "vf")
_src([0x0AF1], "NotoSansGujarati[wdth,wght].ttf", "vf")
_src([0x0BF9], "NotoSansTamil[wdth,wght].ttf", "vf")
_src([0x0E3F], "NotoSansThai[wdth,wght].ttf", "vf")
_src([0x17DB], "NotoSansKhmer[wdth,wght].ttf", "vf")
_src([0x20C0], "NotoSans[wdth,wght].ttf", "vf")
_src(list(range(0x2190, 0x219A)) + [0x2302], "NotoSansSymbols[wght].ttf", "vf")
# U+21A8 is only in Noto Sans Math, drawn heavier than the Symbols arrows: it is synthesized
# instead from Noto Sans Symbols' up-down arrow (U+2195) with a base bar under it, the bar as
# thick as the arrow's shaft and as wide as its head.
_src([0x21A8], "NotoSansSymbols[wght].ttf", "updown_base")
_src(list(range(0x2460, 0x246A)) + list(range(0x2776, 0x2780)), "NotoSansSymbols[wght].ttf", "vf")
_src([0x2219, 0x221F, 0x2229, 0x2236, 0x2261, 0x2310, 0x2320, 0x2321, 0x27E8, 0x27E9],
     "NotoSansMath-Regular.ttf", "static")
_src([0x25A1, 0x25AB, 0x25CB, 0x25E6, 0x2610, 0x2611, 0x2713, 0x2BBD, 0x2BBE],
     "NotoSansSymbols2-Regular.ttf", "static")
_src([0x25AA, 0x25CF, 0x2766], "NotoSansSymbols2-Regular.ttf", "fill")
BOX = [0x2500, 0x2502, 0x250C, 0x2510, 0x2514, 0x2518]
_src(BOX, "NotoSansMono[wdth,wght].ttf", "box")
INTEGRAL = [0x2320, 0x2321]

# In the reference's italics, symbols, arrows, shapes, box drawing and math signs stay upright
# (only shifted); letters, currency signs and the floral heart are slanted. Apodi does the same.
SLANTED = set(range(0x03E2, 0x03F0)) | {0x058F, 0x060B, 0x09F2, 0x09F3, 0x0AF1, 0x0BF9, 0x0E3F,
                                        0x17DB, 0x20C0, 0xFDFC, 0x2766}


class CubicPen(BasePen):
    """Segment pen that turns quadratic curves into exact cubic ones (degree elevation)."""

    def __init__(self, out):
        super().__init__(None)
        self.out = out

    def _moveTo(self, p):
        self.out.moveTo(p)

    def _lineTo(self, p):
        self.out.lineTo(p)

    def _curveToOne(self, p1, p2, p3):
        self.out.curveTo(p1, p2, p3)

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
        c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
        self.out.curveTo(c1, c2, p2)

    def _closePath(self):
        self.out.closePath()

    def _endPath(self):
        self.out.endPath()


def bounds(rec):
    bp = BoundsPen(None)
    rec.replay(bp)
    return bp.bounds


class Noto:
    def __init__(self, folder):
        self.folder = folder
        self._fonts, self._faces, self._gs = {}, {}, {}

    def font(self, name):
        if name not in self._fonts:
            self._fonts[name] = TTFont(os.path.join(self.folder, name))
        return self._fonts[name]

    def axes(self, name):
        f = self.font(name)
        return {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in f["fvar"].axes} if "fvar" in f else {}

    def glyph(self, name, cp, loc=None):
        """(RecordingPen of the decomposed outline, advance) at a variable location."""
        f = self.font(name)
        key = (name, tuple(sorted((loc or {}).items())))
        if key not in self._gs:
            self._gs[key] = f.getGlyphSet(location=loc) if loc else f.getGlyphSet()
        gs = self._gs[key]
        gname = f.getBestCmap()[cp]
        rec = DecomposingRecordingPen(gs)
        gs[gname].draw(rec)
        out = RecordingPen()
        rec.replay(CubicPen(out))
        return out, gs[gname].width

    def static_glyph(self, name, cp, xs, ys):
        """Outline of a static font's glyph emboldened by FreeType (xs/ys: font units added to
        the stroke width horizontally / vertically), as a RecordingPen, and its advance."""
        if name not in self._faces:
            self._faces[name] = freetype.Face(os.path.join(self.folder, name))
        face = self._faces[name]
        face.load_char(chr(cp), freetype.FT_LOAD_NO_SCALE | freetype.FT_LOAD_NO_HINTING)
        outline = face.glyph.outline
        if xs or ys:
            err = freetype.raw.FT_Outline_EmboldenXY(ctypes.byref(outline._FT_Outline),
                                                     int(round(xs)), int(round(ys)))
            assert not err, err
        out = RecordingPen()
        pen = CubicPen(out)
        state = {"open": False}

        def move_to(a, ctx):
            if state["open"]:
                pen.closePath()
            pen.moveTo((a.x, a.y))
            state["open"] = True

        def line_to(a, ctx):
            pen.lineTo((a.x, a.y))

        def conic_to(a, b, ctx):
            pen.qCurveTo((a.x, a.y), (b.x, b.y))

        def cubic_to(a, b, c, ctx):
            pen.curveTo((a.x, a.y), (b.x, b.y), (c.x, c.y))
        outline.decompose(None, move_to=move_to, line_to=line_to, conic_to=conic_to, cubic_to=cubic_to)
        if state["open"]:
            pen.closePath()
        return out, face.glyph.metrics.horiAdvance

    def stem(self, name, loc, italic_angle=0.0):
        """Stem of Noto Sans's l at a location (horizontal extent minus the slant; Noto Sans's I
        has serifs)."""
        rec, _ = self.glyph(name, ord("l"), loc)
        x0, y0, x1, y1 = bounds(rec)
        return (x1 - x0) - (y1 - y0) * abs(math.tan(math.radians(italic_angle)))

    def wght_for_stem(self, name, target, wdth, italic_angle=0.0):
        lo, hi = 100.0, 900.0
        loc = lambda w: {"wght": w, "wdth": wdth}
        for _ in range(16):
            mid = (lo + hi) / 2
            if self.stem(name, loc(mid), italic_angle) < target:
                lo = mid
            else:
                hi = mid
        return round((lo + hi) / 2, 1)


def classify(cp):
    return unicodedata.category(chr(cp))[0]


def add_glyphs(font, noto, targets, ref_bounds, scale_ratio, stem_final, italic, italic_angle, x_height):
    """Draw every reference codepoint `font` lacks from the Noto fonts; return {glyph: target}.

    targets: {cp: reference advance}; scale_ratio: Apodi cap height / Noto cap height in font units;
    stem_final: the style's l stem in Apodi units (what Noto's l is matched to)."""
    s = scale_ratio
    have = {u for g in font for u in g.unicodes}
    latin = "NotoSans-Italic[wdth,wght].ttf" if italic else "NotoSans[wdth,wght].ttf"
    t_slant = math.tan(math.radians(-italic_angle)) if italic else 0.0
    target_stem = stem_final / s                         # in Noto units
    stem400 = noto.stem("NotoSans[wdth,wght].ttf", {"wght": 400, "wdth": 100})
    wcache = {}

    def wght(fname, wdth):
        key = (fname == latin and italic, wdth)
        if key not in wcache:
            name = latin if fname == latin else "NotoSans[wdth,wght].ttf"
            wcache[key] = noto.wght_for_stem(name, target_stem, wdth, italic_angle if name == latin and italic else 0)
        return wcache[key]

    added, report = {}, []
    for cp in sorted(targets):
        if cp in have or cp not in SOURCES:
            continue
        t = targets[cp]
        fname, kind = SOURCES[cp]
        if italic and cp == 0x20C0:
            fname = latin
        gname = "uni%04X" % cp
        assert gname not in font, gname
        if kind == "box":
            rec = box_glyph(noto, fname, cp, s, ref_bounds)
            place(font, gname, cp, rec, t, (1, 0, 0, 1, 0, 0))
            added[gname] = t
            report.append((cp, fname, "box: reference extents", 1.0))
            continue
        # candidates: (recording, natural advance in Noto units, horizontal factor, note)
        cands = []
        if kind == "updown_base":
            w = wght(fname, 100)
            rec, adv = updown_with_base(noto, fname, {"wght": w})
            cands.append((rec, adv, 1.0, f"synthesized from U+2195 wght {w:g}"))
        elif kind == "vf":
            axes = noto.axes(fname)
            wdths = [w for w in (100, 87.5, 75, 62.5) if "wdth" in axes and axes["wdth"][0] <= w] or [100]
            for wd in wdths:
                w = wght(fname, wd)
                loc = {"wght": w}
                if "wdth" in axes:
                    loc["wdth"] = wd
                rec, adv = noto.glyph(fname, cp, loc)
                cands.append((rec, adv, 1.0, f"wght {w:g} wdth {wd:g}"))
        else:
            d = target_stem - stem400 if kind == "static" else 0.0
            # letters may be condensed (stems compensated); symbols and shapes keep their
            # proportions and are scaled down whole if they don't fit
            for k in ((1.0, 0.95, 0.9, 0.85) if classify(cp) == "L" else (1.0,)):
                xs = d + (stem400 + d) * (1 - k) / k if kind == "static" else 0.0
                ys = 0.9 * d
                rec, adv = noto.static_glyph(fname, cp, xs, ys)
                cands.append((rec, adv + xs, k, f"embolden x{xs:+.0f} y{ys:+.0f} k{k:g}" if kind == "static" else "scaled"))
        rec, adv, k, note = min(cands, key=lambda c: (abs(t - c[1] * s * c[2]) / t + 0.5 * abs(1 - c[2])))
        sx, sy = s * k, s
        bb = bounds(rec)
        n = adv * sx
        D = t - n
        if cp in INTEGRAL:
            rec = integral_piece(rec, cp, sx, sy, ref_bounds)
            place(font, gname, cp, rec, t, (1, 0, 0, 1, 0, 0))
            added[gname] = t
            report.append((cp, fname, note + "; reference extents", 1.0))
            continue
        L, R = bb[0] * sx, n - bb[2] * sx
        dx = D * L / (L + R) if (L > 0 and R > 0) else D / 2
        dy, shrink = 0.0, 1.0
        # a symbol much wider than its advance is scaled down about its centre, as in the main fit
        L1, R1 = L + dx, R + (D - dx)
        if classify(cp) in "SPN" and (L1 < min(0, L) - 0.08 * t or R1 < min(0, R) - 0.08 * t):
            shrink = t / n
            sx, sy = sx * shrink, sy * shrink
            n = adv * sx
            D = t - n
            L, R = bb[0] * sx, n - bb[2] * sx
            dx = D * L / (L + R) if (L > 0 and R > 0) else D / 2
            cy = (bb[1] + bb[3]) / 2
            dy = cy * s - cy * sy
        slant = t_slant if (italic and cp in SLANTED and fname != latin) else 0.0
        # x' = sx x + slant (sy y + dy - x_height/2) + dx ; y' = sy y + dy
        xf = (sx, 0, slant * sy, sy, dx + slant * (dy - x_height / 2), dy)
        place(font, gname, cp, rec, t, xf)
        added[gname] = t
        report.append((cp, fname, note, round(shrink, 3)))
    return added, report


def updown_with_base(noto, fname, loc):
    """U+21A8 UP DOWN ARROW WITH BASE: U+2195 plus a bar below its lower tip."""
    rec, adv = noto.glyph(fname, 0x2195, loc)
    x0, y0, x1, y1 = bounds(rec)
    xs = sorted(crossings_y(rec, (y0 + y1) / 2))
    shaft = xs[1] - xs[0] if len(xs) >= 2 else (x1 - x0) / 8
    # the arrow keeps its height; it moves up so the bar sits where its lower tip was
    lift = 2 * shaft
    out = RecordingPen()
    for op, args in rec.value:
        out.value.append((op, tuple((x, y + lift) for x, y in args)))
    out.moveTo((x0, y0))
    out.lineTo((x1, y0))
    out.lineTo((x1, y0 + shaft))
    out.lineTo((x0, y0 + shaft))
    out.closePath()
    return out, adv


def crossings_y(rec, y):
    """x where the outline crosses height y (straight segments and flattened curves)."""
    out, cur, start = [], None, None
    for op, args in rec.value:
        if op == "moveTo":
            cur = start = args[0]
            continue
        if op == "closePath":
            seg = [cur, start]
        elif op == "lineTo":
            seg = [cur, args[0]]
        elif op == "curveTo":
            p0, p1, p2, p3 = cur, *args
            seg = [tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * d
                         for a, b, c, d in zip(p0, p1, p2, p3)) for t in [i / 16 for i in range(17)]]
        else:
            continue
        for (ax, ay), (bx, by) in zip(seg, seg[1:]):
            if (ay - y) * (by - y) < 0:
                out.append(ax + (y - ay) * (bx - ax) / (by - ay))
        cur = seg[-1] if op != "closePath" else start
    return out


def place(font, gname, cp, rec, width, xf):
    g = font.newGlyph(gname)
    g.unicodes = [cp]
    g.width = int(width)
    rec.replay(TransformPen(g.getPen(), xf))


def _remap(v, c_src, half, c_dst, lo_dst, hi_dst, k):
    if abs(v - c_src) <= half + 1:
        return c_dst + (v - c_src) * k
    return lo_dst if v < c_src else hi_dst


def box_glyph(noto, fname, cp, s, ref_bounds):
    """Box drawing: Noto Sans Mono's light line weight, at the reference's extents (lines run to the
    reference's bounding box so they join their neighbours and the next and previous rows)."""
    hrec, _ = noto.glyph(fname, 0x2500, {"wght": 400, "wdth": 100})
    vrec, _ = noto.glyph(fname, 0x2502, {"wght": 400, "wdth": 100})
    hb, vb = bounds(hrec), bounds(vrec)
    cy_n, hh = (hb[1] + hb[3]) / 2, (hb[3] - hb[1]) / 2
    cx_n, hv = (vb[0] + vb[2]) / 2, (vb[2] - vb[0]) / 2
    rh, rv = ref_bounds[0x2500], ref_bounds[0x2502]
    cy_r, cx_r = (rh[1] + rh[3]) / 2, (rv[0] + rv[2]) / 2
    rb = ref_bounds[cp]
    rec, _ = noto.glyph(fname, cp, {"wght": 400, "wdth": 100})
    out = RecordingPen()
    for op, args in rec.value:
        pts = [(_remap(x, cx_n, hv, cx_r, rb[0], rb[2], s), _remap(y, cy_n, hh, cy_r, rb[1], rb[3], s))
               for x, y in args]
        out.value.append((op, tuple(pts)))
    return out


def integral_piece(rec, cp, sx, sy, ref_bounds):
    """Top / bottom half integral: scaled like the other glyphs, the hook end at the reference's
    extent on its side, the stem's open end stretched to the reference's extent on the other, and
    the stem's left edge on the reference top piece's left edge, so the halves join across lines."""
    b = bounds(rec)
    rb = ref_bounds[cp]
    top = cp == 0x2320
    end = b[1] if top else b[3]
    ends = [x for op, args in rec.value for x, y in args if abs(y - end) < 1]
    dx = ref_bounds[0x2320][0] - min(ends) * sx
    dy = rb[3] - b[3] * sy if top else rb[1] - b[1] * sy
    out = RecordingPen()
    for op, args in rec.value:
        pts = []
        for x, y in args:
            Y = y * sy + dy
            if abs(y - end) < 1:
                Y = rb[1] if top else rb[3]
            pts.append((x * sx + dx, Y))
        out.value.append((op, tuple(pts)))
    return out
