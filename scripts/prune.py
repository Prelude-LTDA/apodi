"""Reduce Apodi UFOs to the glyphs that ship (plus their component/feature closure).

Open Sans's sources carry ~3,400 glyphs, of which ~1,300 ship. This drops the rest from
the UFOs and prunes features.fea so it only references remaining glyphs.
"""
import io
import os
import sys
import tempfile

from fontTools import subset
from fontTools.feaLib import ast
from fontTools.feaLib.parser import Parser
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_fonts import FEATURES  # noqa: E402


def closure(ufo, wanted):
    """Glyph names reachable from `wanted` through components and the kept features."""
    import ufo2ft
    ttf = ufo2ft.compileTTF(ufo, useProductionNames=False, removeOverlaps=False)
    opts = subset.Options()
    opts.layout_features = FEATURES
    opts.glyph_names = True
    opts.notdef_outline = True
    opts.name_IDs = ["*"]
    sub = subset.Subsetter(opts)
    sub.populate(glyphs=sorted(set(wanted) & set(ttf.getGlyphOrder())) + [".notdef"])
    sub.subset(ttf)
    keep = set(ttf.getGlyphOrder())
    # components are flattened by ufo2ft filters at compile time; keep UFO component bases too
    todo = list(keep)
    while todo:
        g = todo.pop()
        if g in ufo:
            for c in ufo[g].components:
                if c.baseGlyph not in keep:
                    keep.add(c.baseGlyph)
                    todo.append(c.baseGlyph)
    return keep


def _name(g):
    return g if isinstance(g, str) else getattr(g, "glyph", None)


def _filter_container(c, keep):
    """Return (container, ok). Classes are filtered in place; a missing single glyph -> not ok."""
    if isinstance(c, ast.GlyphName):
        return c, c.glyph in keep
    if isinstance(c, ast.GlyphClass):
        c.glyphs = [g for g in c.glyphs if _name(g) in keep]
        c.original, c.curr = [], 0
        return c, bool(c.glyphs)
    if isinstance(c, ast.GlyphClassName):
        return c, bool(c.glyphclass.glyphSet())
    if isinstance(c, ast.MarkClassName):
        return c, True
    return c, True


def _filter_pairwise(src, dst, keep):
    a = [_name(g) for g in src.glyphSet()]
    b = [_name(g) for g in dst.glyphSet()]
    pairs = [(x, y) for x, y in zip(a, b) if x in keep and y in keep]
    return (ast.GlyphClass([x for x, _ in pairs]), ast.GlyphClass([y for _, y in pairs]), bool(pairs))


def prune_fea(text, keep, all_names):
    doc = Parser(io.StringIO(text), glyphNames=set(all_names), followIncludes=False).parse()
    empty_lookups = set()

    def visit(block):
        out = []
        for s in block.statements:
            if isinstance(s, ast.GlyphClassDefinition):
                s.glyphs, ok = _filter_container(s.glyphs, keep)
                out.append(s)  # an empty definition is harmless; rules using it get dropped
                continue
            if isinstance(s, (ast.FeatureBlock, ast.LookupBlock)):
                visit(s)
                rules = [x for x in s.statements if not isinstance(
                    x, (ast.Comment, ast.LookupFlagStatement, ast.ScriptStatement, ast.LanguageStatement))]
                if isinstance(s, ast.LookupBlock) and not rules:
                    empty_lookups.add(s.name)
                    continue
                out.append(s)
                continue
            if isinstance(s, ast.LookupReferenceStatement) and s.lookup.name in empty_lookups:
                continue
            if isinstance(s, ast.SingleSubstStatement):
                src, dst = s.glyphs[0], s.replacements[0]
                if len(src.glyphSet()) > 1 and len(dst.glyphSet()) == len(src.glyphSet()):
                    s.glyphs[0], s.replacements[0], ok = _filter_pairwise(src, dst, keep)
                else:
                    _, ok1 = _filter_container(src, keep)
                    _, ok2 = _filter_container(dst, keep)
                    ok = ok1 and ok2
                ok = ok and all(_filter_container(c, keep)[1] for c in list(s.prefix) + list(s.suffix))
                if ok:
                    out.append(s)
                continue
            if isinstance(s, ast.LigatureSubstStatement):
                ok = all(_filter_container(c, keep)[1] for c in list(s.glyphs) + list(s.prefix) + list(s.suffix))
                ok = ok and _name(s.replacement) in keep if isinstance(s.replacement, (str, ast.GlyphName)) else ok
                if ok:
                    out.append(s)
                continue
            if isinstance(s, (ast.MultipleSubstStatement, ast.AlternateSubstStatement)):
                cs = list(getattr(s, "glyph", []) and [s.glyph]) + list(getattr(s, "prefix", [])) + list(getattr(s, "suffix", []))
                ok = all(_filter_container(c, keep)[1] for c in cs if not isinstance(c, str)) and \
                    all((_name(c) in keep) for c in cs if isinstance(c, str))
                if ok:
                    out.append(s)
                continue
            out.append(s)
        block.statements = out

    visit(doc)
    return doc.asFea()


def prune_ufo(ufo, keep):
    for g in [g for g in list(ufo.keys()) if g not in keep]:
        del ufo[g]
    for k in list(ufo.groups):
        ufo.groups[k] = [g for g in ufo.groups[k] if g in keep]
        if not ufo.groups[k]:
            del ufo.groups[k]
    for (a, b) in list(ufo.kerning):
        if (not a.startswith("public.kern") and a not in keep) or (not b.startswith("public.kern") and b not in keep) \
                or (a.startswith("public.kern") and a not in ufo.groups) or (b.startswith("public.kern") and b not in ufo.groups):
            del ufo.kerning[(a, b)]
    lib = ufo.lib
    lib["public.glyphOrder"] = [g for g in lib.get("public.glyphOrder", []) if g in keep]
    if "public.postscriptNames" in lib:
        lib["public.postscriptNames"] = {k: v for k, v in lib["public.postscriptNames"].items() if k in keep}
    if "public.skipExportGlyphs" in lib:
        lib["public.skipExportGlyphs"] = [g for g in lib["public.skipExportGlyphs"] if g in keep]
    for f in lib.get("com.github.googlei18n.ufo2ft.filters", []):
        if "include" in f:
            f["include"] = sorted({g for g in f["include"] if g in keep})
    if "org.apodi.lockedAdvanceWidths" in lib:
        lib["org.apodi.lockedAdvanceWidths"] = {k: v for k, v in lib["org.apodi.lockedAdvanceWidths"].items() if k in keep}
