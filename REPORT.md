# Apodi: build report

Date: 2026-10-17. Version 1.001. All numbers below come from `./build.sh check` and `build/fit_report.json` for the
binaries in `fonts/`.

## 1. Inventory

**Reference fonts available locally** (15 files, read-only, never copied): Aptos (Regular), Bold, Italic, Bold Italic,
ExtraBold, ExtraBold Italic, Black; Aptos Narrow Regular, Bold, Italic, Bold Italic; Aptos Display Regular, Bold,
Italic, Bold Italic. There is no Light, SemiBold or Black Italic.

- **Shared metrics:** all use unitsPerEm 2048, hhea and typo 1923/−577/0, win 2068/563 and USE_TYPO_METRICS. Cap
  height is 1346 and the italic angle is −12°.
- **x-height:** 974 (Display 974–979, Narrow 1016–1026).
- **Figures and features:** default figures are tabular (1094 units in Regular). `pnum`, `onum`, `case`, `frac`,
  `sups`, `ss01–03` and `liga` (`ff fi fl`) exist as features.

**Built:** the 12 styles of Apodi, Apodi Narrow and Apodi Display (Regular, Bold, Italic, Bold Italic each). ExtraBold
and Black are not built.

**Base:** Open Sans sources from googlefonts/opensans, commit `bd7e37632246368c60fdcbd374dbf9bad11969b6` (v3.003).

- **Files used:** `sources/OpenSans-{Roman,Italic}.designspace`, with UFO masters Thin/Regular/Bold/ExtraBold ×
  Normal/Condensed.
- **License:** SIL OFL 1.1, with no Reserved Font Name.
- **Same sources as the published font:** the repository's published variable font is built from these sources
  (checked: 0 advance differences).
- **Not used:** the repository's `original source/*.glyphs` files. They do not match the published fonts (different
  glyph set and Condensed masters).

**Coverage:** 1,002 of 1,086 codepoints (italics: 1,002 of 1,085).

- **Complete:** Basic Latin, Latin-1, Latin Extended-A, Latin Extended-B/IPA and general punctuation, including
  ZWJ/ZWNJ/bidi controls.
- **Recovered:** 138 of the 222 codepoints the published Open Sans fonts lack. Their glyphs are in the Open Sans
  sources but not shipped by Open Sans:
  - currency: ₹ ₽ ₺ ₩ ₱ ₦ ₿ ₴ ₸ ₼ ₾ ₡ ₢ ₥ ₨ ₭ ₮ ₯ ₰ ₲ ₳ ₵ ₶ ₷ ₻ ₠
  - fractions ⅓–⅚, and ‽ ‾ ℗ ℳ ◌
  - Latin Extended-B/IPA letters, Greek symbols and format controls
- **Missing (84):**
  - Coptic: U+03E2–03EF
  - other scripts' currency signs: U+058F ֏, U+060B ؋, U+09F2, U+09F3, U+0AF1, U+0BF9, U+0E3F ฿, U+17DB, U+20C0
    (upright only), U+FDFC ﷼
  - arrows: U+2190–2199 and U+21A8
  - math ∙ ∟ ∩ ∶ ≡; technical ⌂ ⌐ ⌠ ⌡
  - circled digits ①–⑩ and ❶–❿
  - box drawing ─ │ ┌ ┐ └ ┘; shapes □ ▪ ▫ ○ ● ◦
  - other: ☐ ☑ ✓ ❦, ⟨ ⟩, ⮽ ⮾

## 2. Method (per style)

1. **Scale.** All outlines are scaled uniformly by 1346/1462 = 0.92066, so cap height matches. The x-height ends up at
   1012–1035, about 4% above the reference's 974. In Narrow it is 1014 against 1016.
2. **Weight.** The base is Open Sans wght 450 (Regular) and 700 (Bold) at wdth 100, chosen by eye against the reference
   at equal cap height. At every other width the wght is re-solved so that the stem of `I`, measured on Open Sans
   instances, keeps the base thickness. For example, Regular uses wght 492 at wdth 75 and 421 at wdth 100 with 6%
   stretch.
3. **Width choice.** Each encoded glyph picks the instance whose advance is closest to the reference advance.
   - Candidates: wdth 75…100 in steps of 2.5, plus horizontal stretch ×1.015…1.06 at wdth 100 and ×0.985/0.97 at
     wdth 75.
   - Cost: 1% of stretch counts as much as 0.5% of width error.
   - Composites, alternates and ligatures follow their base glyph.
4. **Exact advance.** The remaining difference goes into the sidebearings, split in proportion to the existing left and
   right sidebearings. Accented glyphs reuse their base's shift, so marks stay aligned. A symbol that would otherwise
   overlap its neighbours by more than 8% of its width is scaled down uniformly about its centre instead.
5. **Kerning.** Open Sans kerning is replaced with the reference values, keyed by codepoint pair (and by `ff`/`fi`/`fl`
   sequence for ligatures).
   - The values are compressed into about 155 UFO kern groups and ~1,950 class pairs, and compiled with IgnoreMarks.
   - Mark positioning (`mark`/`mkmk`) comes from Open Sans anchors, transformed with each glyph.
6. **Vertical metrics.** hhea, typo and win values are copied from the reference; USE_TYPO_METRICS is set.
7. **Ligatures.** `liga` keeps `ff`, `fi` and `fl` at the reference advances; `ffi`/`ffl` are removed to match.
8. **Letter shapes.** Besides the M and the redrawn G K C c S s and italic obliques (§5), two Open Sans alternates
   were checked against the reference renderings and promoted to default: J.salt (J sitting on the baseline, all
   styles) and a.ss01 (double-storey a, italics). The double-storey (binocular) g stays the default, as in the
   reference; the single-storey g is still reachable via `salt`/`ss01`/`ss02`.
9. **Build.** fontmake (cubic to quadratic, overlaps removed, unhinted), then subsetting to the shipped glyph set, then
   WOFF2.

### Residual adjustments

The residual is the sidebearing change divided by the advance, per fitted glyph (1,003 per style). It includes the
reference's very wide spacing accents (´ ` ¸ ˙, 1,130 units).

| Style | at wdth 100 | narrower wdth | stretched (k≠1) | scaled-down symbols | median abs residual | p90 | >5% | >10% |
|---|---|---|---|---|---|---|---|---|
| Regular | 683 | 320 | 483 | ® | 0.7% | 5.2% | 106 | 63 |
| Bold | 580 | 423 | 389 | ® | 0.6% | 7.7% | 136 | 69 |
| Italic | 888 | 115 | 827 | ® | 1.6% | 11.2% | 312 | 118 |
| Bold Italic | 848 | 155 | 783 | ‹ › ® | 1.0% | 9.1% | 258 | 92 |
| Narrow Regular | 203 | 800 | 147 | ® | 0.8% | 2.1% | 71 | 51 |
| Narrow Bold | 142 | 861 | 114 | ₧ ® ″ ™ | 0.5% | 1.8% | 79 | 52 |
| Narrow Italic | 485 | 518 | 342 | ® | 0.6% | 7.8% | 133 | 84 |
| Narrow Bold Italic | 261 | 742 | 185 | « » ‹ › ₧ ® ™ | 0.7% | 4.3% | 93 | 52 |
| Display Regular | 389 | 614 | 295 | ® | 0.7% | 4.1% | 88 | 55 |
| Display Bold | 352 | 651 | 274 | ® | 0.6% | 3.7% | 88 | 61 |
| Display Italic | 661 | 342 | 578 | ® | 0.9% | 9.1% | 230 | 88 |
| Display Bold Italic | 645 | 358 | 540 | ® | 0.6% | 8.2% | 161 | 85 |

**Largest residuals among letters:**

- **Regular:** OE +15%, IJ +14%, ª º +18–19%, AE +9%, ƒ −21%. C c G K S s e f, g, J and a are within about 2%
  (C and c were +11% before they were cut out of O and o).
- **Italic:** F +14%, E +9%. The redrawn C c S s e f are within about 2% (before: C +18%, c +16%, S/s +13%, e +8%);
  in Bold Italic, S/s and K are at +5–6%.

## 3. Validation

**(a) `scripts/check_metrics.py`** found 0 mismatches in all 12 styles for advance widths (1,002 codepoints each),
vertical metrics, ligatures and kerning.

| Style | kern pairs tested |
|---|---|
| Regular / Bold | 68,713 / 68,949 |
| Italic / Bold Italic | 61,509 / 61,745 |
| Narrow (R / B / I / BI) | 69,806 / 69,594 / 62,324 / 63,192 |
| Display (R / B / I / BI) | 69,087 / 69,323 / 62,522 / 62,758 |

Each pair is shaped as a two-character string with HarfBuzz in both fonts. Six cases are not counted: in Narrow Bold
Italic, Display Italic and Display Bold Italic, the reference decomposes ﬁ/ﬂ (U+FB01/FB02) after `f` and re-ligates
them as `ff`+`i`, so `f`+`ﬁ` differs by 1 unit.

**(b) `scripts/linebreak.py`** found 0 differing breaks.

- **Paragraphs:** 20 business paragraphs (7 English, 7 Portuguese, 6 Italian), with amounts in $, €, £ and R$,
  percentages and dates.
- **Layouts:** 11/12/10/14 pt at 451 pt, 11 pt at 216 and 523 pt, 9 pt at 160 pt, and 8 pt at 120 pt, each with
  kerning on and off. A greedy breaker measures the HarfBuzz-shaped width of each candidate line.
- **Paragraph result:** 320 cases per style, about 14,000 lines in total, 0 differing breaks.
- **Narrow cells:** 34 spreadsheet cell strings at Excel column widths of 8.43, 10, 12, 15 and 20 characters (11 pt),
  checking both whether the cell fits and where it wraps. Result: 340 cases per style, 0 differences.

**(c) Renderings** (regenerate with `APTOS_DIR=... ./build.sh images`):

- **`docs/comparison/compare_<Style>.png` (12 images):** reference and Apodi rows for the alphabet, figures and
  currency, accents and punctuation, a paragraph (identical breaks in all 12), and an overlay strip. These contain
  reference renderings, so they are local only and git-ignored.
- **`docs/comparison/M_with_reference.png`:** local only.
- **`docs/images/M_before_after.png`:** Open Sans M against Apodi Regular, Bold and Italic. Committed.
- **`docs/images/revisions.png`:** the G K M, C c S s and italic obliques rows, Aptos / Apodi before / Apodi after, in
  Regular and Bold (with their italics); made by `scripts/revisions.py --aptos`. It contains reference renderings, so
  it is git-ignored like `docs/comparison/`.
- **`docs/images/revisions-apodi.png`:** the same rows without the reference, Apodi before / after, in Regular, Bold,
  Narrow Bold and Display Regular. Committed.
- **`docs/images/specimen.png`:** all 12 styles. Committed.

## 4. Visible design differences

- **Lowercase** is about 4% taller, because caps are matched.
- **Matching shapes:** g (binocular), J (on the baseline) and the italic a (double-storey) match the reference's
  structure.
- **Italic overall:** Open Sans Italic is narrower and more cursive than the reference's sloped roman. e, f (and
  ff fi fl), c, C, s and S are now obliques of the roman forms, which removes most of the extra space they carried; F
  and E still carry visibly extra space. The other lowercase keeps Open Sans's cursive italic structure.
- **C, c, S, s** are cut out of O, o and 8, with flat horizontal terminals and a wider aperture than Open Sans's;
  their spacing is now close to the reference's. The S spine is the 8's waist, a little lighter than the bowls in
  the Bold styles.
- **G** has no spur (Open Sans's Komi Sje); **K** is Open Sans's Cyrillic Ka.
- **Q, R, t, f, j, l, y:** terminals, tails and legs follow Open Sans.
- **Figures 1-2-3-4-5-6-9** follow Open Sans's shapes; their widths are identical to the reference.
- **Punctuation:** quotes and commas are comma-shaped where the reference uses wedges. The bullet • is smaller, and the
  dots are smaller and round.
- **Scaled-down symbols:** ®, and in some styles ™ ″ ₧ « » ‹ ›, are smaller than in Open Sans.
- **Spacing accents** have very wide advances in the reference; Apodi centres Open Sans's small accents in that space.
- **M:** Apodi's vertex sits at 25% of the cap height; the reference's sits at about a third.
- **Narrow** keeps Open Sans's condensed proportions.

## 5. Letter shapes redrawn in the pipeline

All of these are made in `scripts/build_sources.py` on every interpolated Open Sans instance before fitting, so the
width choice and the locked advance treat the new drawing like any other glyph. Composites follow their base: their
marks move with the base's anchors, and accented forms (Ğ Ķ Ç ç Ş š é ę …) and the Cyrillic/Greek letters built on
these glyphs inherit the change.

- **M.** The two on-curve points at the bottom of the V and the two crotch points move up by 25% of the cap height
  (`M_VERTEX_RAISE`): 366 units in Open Sans space, 337 in Apodi. In italics they also move along the 12° slant.
- **G, K.** Drawn with Open Sans's Cyrillic Komi Sje (Ԍ, `uni050C`) and Ka (К, `afii10028`), present in every master
  of both designspaces. The Latin names, kerning and groups stay.
- **C, c.** O and o minus a rectangle from the horizontal centre to past the right edge, from 30% to 70% of the
  height (`CUT_C`, via skia-pathops), which leaves flat horizontal terminals.
- **S.** The 8 minus its upper-right quarter (centre to right edge, waist to 74% of the height) and lower-left
  quarter (left edge to centre, 26% to the waist). Open Sans's 8 is one outer contour with two counters; its waist
  corners lie on the edges of two crossing S-curves. The cuts are bounded at the waist by curves tangent to those
  edges, so no stub of the other diagonal remains and the spine is one smooth stroke.
- **s.** The same cut on an x-height 8: Open Sans has no x-height 8 (its oldstyle 8 is full height, and ȣ is
  open-topped), so the cap 8 is interpolated at the weight at which, scaled to the height of o, its top stroke matches
  s's, then narrowed so its bowls match o's stem.
- **Italic e f c C s S** (with ę and the ff fi fl ffi ffl ligatures): the glyph of the roman instance that the
  matching upright style uses at the same wdth and stretch (stem solved the same way), slanted by the italic angle
  (−12°) about half the x-height. Anchors are slanted with them.

## 6. Residual issues and risks

1. **Missing characters:** 84 reference characters are missing (§1). Text that uses them falls back to another font
   with different widths.
2. **Optional figure styles and features are not width-matched.** Proportional and oldstyle figures, superscripts,
   subscripts and fractions (`pnum`, `onum`, `sups`/`subs`/`frac`), all-caps forms (`case`) and small caps keep Open
   Sans widths.
3. **Hinted layouts:** the reference is TrueType-hinted. Old Windows-style layouts round each advance to whole pixels
   after hinting; there, 6–12 of 318 Latin glyphs are 1 px off at 13–20 ppem. Modern layout engines use unrounded
   widths and are unaffected.
4. **ﬁ/ﬂ after `f`** in three styles: a 1-unit difference, see §3(a).
5. **Italic spacing:** F and E still look loose (§4).
6. **Bold** may read slightly heavier than the reference; tune `BASE_WGHT` if needed.
7. **Interpolation:** the 12 UFOs mostly share point structure but are fitted independently; the cut C c S s are
   boolean results and are not point-compatible across styles. They are separate styles, and no variable font is
   offered.
