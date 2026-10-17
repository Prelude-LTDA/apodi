# Apodi: build report

Date: 2026-10-17. Version 1.000. All numbers below come from `./build.sh check` and `build/fit_report.json` for the
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
8. **Letter shapes.** Besides the M (§5), two Open Sans alternates were checked against the reference renderings and
   promoted to default: J.salt (J sitting on the baseline, all styles) and a.ss01 (double-storey a, italics). The
   double-storey (binocular) g stays the default, as in the reference; the single-storey g is still reachable via
   `salt`/`ss01`/`ss02`.
9. **Build.** fontmake (cubic to quadratic, overlaps removed, unhinted), then subsetting to the shipped glyph set, then
   WOFF2.

### Residual adjustments

The residual is the sidebearing change divided by the advance, per fitted glyph (1,003 per style). It includes the
reference's very wide spacing accents (´ ` ¸ ˙, 1,130 units).

| Style | at wdth 100 | narrower wdth | stretched (k≠1) | scaled-down symbols | median abs residual | p90 | >5% | >10% |
|---|---|---|---|---|---|---|---|---|
| Regular | 711 | 292 | 511 | ® | 0.7% | 8.6% | 134 | 83 |
| Bold | 599 | 404 | 426 | ® | 0.6% | 9.3% | 150 | 78 |
| Italic | 919 | 84 | 858 | ® | 2.5% | 13.4% | 367 | 145 |
| Bold Italic | 872 | 131 | 814 | ‹ › ® | 1.7% | 13.2% | 289 | 128 |
| Narrow Regular | 231 | 772 | 175 | ® | 0.8% | 2.4% | 71 | 51 |
| Narrow Bold | 170 | 833 | 142 | ₧ ® ″ ™ | 0.5% | 2.0% | 79 | 52 |
| Narrow Italic | 535 | 468 | 409 | ® | 0.6% | 7.3% | 125 | 54 |
| Narrow Bold Italic | 303 | 700 | 224 | « » ‹ › ₧ ® ™ | 0.7% | 5.6% | 113 | 49 |
| Display Regular | 415 | 588 | 315 | ® | 0.7% | 4.7% | 99 | 55 |
| Display Bold | 378 | 625 | 308 | ® | 0.6% | 6.1% | 106 | 61 |
| Display Italic | 706 | 297 | 623 | ® | 0.9% | 9.7% | 257 | 89 |
| Display Bold Italic | 690 | 313 | 593 | ® | 0.7% | 10.1% | 197 | 103 |

**Largest residuals among letters:**

- **Regular:** C/c and their accented forms +11%, OE +15%, IJ +14%, ª º +18–19%, AE +9%, ƒ −21%. g, J and a are within
  about 1%.
- **Italic,** even at the 6% stretch limit: C +18%, c +16%, F +14%, S/s +13%, E +9%, V Y e R +8%. Open Sans Italic is
  simply narrower than the reference italic.

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
- **`docs/images/specimen.png`:** all 12 styles. Committed.

## 4. Visible design differences

- **Lowercase** is about 4% taller, because caps are matched.
- **Matching shapes:** g (binocular), J (on the baseline) and the italic a (double-storey) match the reference's
  structure.
- **Italic overall:** the biggest difference. Open Sans Italic is narrower and more cursive than the reference's sloped
  roman. Even with 6% stretch, C, c, e, s, F, S and E carry visibly extra space. It is the best candidate for
  redrawing: wider c/e/s/o and a less cursive structure.
- **Italic f** descends below the baseline. A non-descending `f.ss02` exists, but the `f_f` ligature is a separate
  drawing and would need redrawing too.
- **C, c, G, S, s:** Open Sans's apertures are narrower, so these letters get extra sidebearings (C and c +11%) and
  read as looser spacing. G keeps Open Sans's spur and bar.
- **Q, R, K, t, f, j, l, y:** terminals, tails and legs follow Open Sans.
- **Figures 1-2-3-4-5-6-9** follow Open Sans's shapes; their widths are identical to the reference.
- **Punctuation:** quotes and commas are comma-shaped where the reference uses wedges. The bullet • is smaller, and the
  dots are smaller and round.
- **Scaled-down symbols:** ®, and in some styles ™ ″ ₧ « » ‹ ›, are smaller than in Open Sans.
- **Spacing accents** have very wide advances in the reference; Apodi centres Open Sans's small accents in that space.
- **M:** Apodi's vertex sits at 16% of the cap height; the reference's sits at about a third. Try `M_VERTEX_RAISE` =
  0.25–0.33.
- **Narrow** keeps Open Sans's condensed proportions.

## 5. The M

The two on-curve points at the bottom of the V and the two crotch points move up by 16% of the cap height: 234 units in
Open Sans space, 215 in Apodi. In italics they also move along the 12° slant. The change is made in `modify_M()` on
every interpolated instance before fitting, so Ḿ, Greek Μ and Cyrillic М inherit it.

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
5. **Italic spacing** looks loose (§4).
6. **Bold** may read slightly heavier than the reference; tune `BASE_WGHT` if needed.
7. **Interpolation:** the 12 UFOs share point structure but are fitted independently. They are separate styles, and no
   variable font is offered.
