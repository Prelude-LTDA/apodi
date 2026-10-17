# Editing Apodi

## The sources

The UFO 3 files and the designspace in `sources/` are the source of truth:

```
sources/
  Apodi.designspace          12 sources on Weight / Width / Optical size + discrete Italic axis
  Apodi-{Regular,Bold,Italic,BoldItalic}.ufo
  ApodiNarrow-{...}.ufo      (Width 87.5)
  ApodiDisplay-{...}.ufo     (Optical size 24)
  glyphset.txt               glyphs that ship; the build subsets to these (+ closure)
```

Each UFO is one complete static style. Contours are cubic and keep the point structure of
Open Sans's sources. Accented letters are components, so a change to `e` carries over to
`é ê ë ...`. Anchors (`top`, `_top`, ...) drive mark positioning, and `features.fea` holds the
substitution features. Kerning lives in `kerning.plist` with `public.kern1/2` groups;
fontmake generates `kern`, `mark` and `mkmk` from these at build time.

Editors that open the sources directly:

* [Fontra](https://fontra.xyz) (open source, browser or desktop): open `Apodi.designspace`
  or any single UFO.
* [FontForge](https://fontforge.org) (open source): open a single `.ufo`.
* Glyphs 3 opens UFOs (File > Open). Save back as UFO, not `.glyphs`, so the
  repository stays editor-neutral.
* RoboFont, and anything else built on UFO 3.

The masters share Open Sans's point structure, but each glyph's width, stretch and weight
were chosen per style. Interpolating between sources therefore gives no designed
intermediate style. Treat each UFO as its own drawing.

## The one rule: keep the advance widths and kerning

Metric compatibility comes from the numbers, not the shapes:

* **Advance widths.** Each UFO's lib stores the fitted width of every metric-bearing glyph
  under `org.apodi.lockedAdvanceWidths`. Change a glyph's *shape* freely, but leave its
  *width* alone. To rebalance spacing, move the outline inside the fixed width: a change to
  the left sidebearing must be paid for by the right one. In Glyphs or Fontra, shift the
  outline instead of editing one sidebearing alone; afterwards the width field should still
  read the same number.
* **Kerning.** Don't edit `kerning.plist` or the `public.kern*` groups. Every value there
  comes from the reference pairs.
* **Vertical metrics.** Leave `ascender`/`descender`/`openTypeHhea*`/`openTypeOS2Typo*`/`Win*`
  and `unitsPerEm` (2048) alone. Outlines may go above or below them; line spacing won't change.
* **Ligatures.** The `liga` feature forms only `ff`, `fi` and `fl`, as the reference does.
  `ffi` and `ffl` are left as `ff` + `i`/`l`. Adding ligatures changes line widths.
* **New glyphs.** These are free to add, unless the character is one of the 84 the reference
  has and Apodi lacks (see REPORT.md). Those need the reference's advance width to stay
  compatible: run `./build.sh fit` after adding them to the Open Sans-derived sources, or
  set the width by hand from `build/metrics/ref_*.json`.

`./build.sh fonts` runs `scripts/check_locked.py` first and warns about every glyph whose
width moved.

## Rebuilding the binaries

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./build.sh fonts
```

This runs `fontmake -u sources/*.ufo -o ttf` (cubic to quadratic, overlaps removed,
production glyph names, unhinted). It then subsets to `sources/glyphset.txt` with the same
OpenType features Open Sans ships, and writes `fonts/ttf/*.ttf` and `fonts/woff2/*.woff2`.
`SOURCE_DATE_EPOCH` is fixed, so the same sources always give the same bytes.

You can also call fontmake directly on the designspace. The output is the same fonts,
without the subsetting step:

```sh
fontmake -m sources/Apodi.designspace -o ttf --output-dir build/ttf
```

From Glyphs, File > Export of a UFO works for a quick look. For release files use
`./build.sh fonts`, so that subsetting and naming stay consistent.

## Re-running the metric checks after editing

```sh
APTOS_DIR=/path/to/folder/with/aptos/ttfs ./build.sh check
```

* `scripts/check_metrics.py` compares each built style with its reference: advance width of
  every shared codepoint, all vertical metric fields, shaped width of every reference
  kerning pair (HarfBuzz) and the ligature sequences. Expected: 0 mismatches. The six
  `f`+`ﬁ`/`ﬂ` presentation-form cases are reported apart, because the reference
  decomposes U+FB01/FB02.
* `scripts/linebreak.py` breaks 20 English/Portuguese/Italian business paragraphs at 8
  size/column combinations, with kerning on and off, plus spreadsheet cells at Excel
  column widths for Narrow. It compares every line break. Expected: 0 differences.
* `./build.sh images` refreshes the side-by-side PNGs in `docs/comparison/` (local only,
  git-ignored) for visual review.

The reference fonts are only read, never copied. Pass their folder with `APTOS_DIR` or `--aptos`.

## Changing the fit itself

The fitting parameters sit at the top of `scripts/build_sources.py`:

* `BASE_WGHT`: Open Sans weight used for Regular and Bold.
* `WDTH_GRID`, `STRETCH_WIDE`, `STRETCH_NARROW`, `STRETCH_COST`: candidate widths, and the
  limits on horizontal scaling.
* `M_VERTEX_RAISE`: the M vertex height.
* `DEFAULT_ALTERNATES`: Open Sans alternates promoted to default. Currently J.salt (J on the
  baseline) everywhere, plus a.ss01 (double-storey a) in italics. The binocular g is
  deliberately left as the default, because the reference uses it too.

Then run `APTOS_DIR=... ./build.sh fit`. This **regenerates `sources/` from scratch** and
discards hand edits, so make design changes in `build_sources.py` (as with the M), or
re-apply them after refitting.
