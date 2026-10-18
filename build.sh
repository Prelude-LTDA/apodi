#!/usr/bin/env bash
# Apodi build entry point.
#
#   ./build.sh fonts     UFO sources -> fonts/ttf + fonts/woff2        (no reference fonts needed;
#                        first checks the locked advance widths in the UFOs)
#   ./build.sh check     metric + line-break checks of fonts/ vs the reference   (needs APTOS_DIR)
#   ./build.sh images    side-by-side PNGs (docs/comparison, local only) + docs/images
#   ./build.sh fit       regenerate sources/ from Open Sans + reference metrics  (needs APTOS_DIR;
#                        OVERWRITES sources/ -- only for re-fitting, not after hand edits)
#   ./build.sh all       fit + fonts + check + images
#
# PYTHON defaults to .venv/bin/python. Scripts that read the reference fonts or downloaded
# files run with `python -I` (isolated mode).
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-.venv/bin/python}"
# reproducible binaries: fixed head.created/modified unless the caller sets it
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1792195200}"

need_aptos() {
  if [ -z "${APTOS_DIR:-}" ]; then
    echo "Set APTOS_DIR to a local folder with the reference .ttf files (read-only; nothing is copied)." >&2
    exit 2
  fi
}

do_fit() {
  need_aptos
  bash scripts/fetch_opensans.sh .opensans
  bash scripts/fetch_noto.sh .noto
  mkdir -p build/metrics
  for pair in "Aptos.ttf:Regular" "Aptos Bold.ttf:Bold" "Aptos Italic.ttf:Italic" "Aptos Bold Italic.ttf:BoldItalic" \
              "Aptos Narrow.ttf:NarrowRegular" "Aptos Narrow Bold.ttf:NarrowBold" "Aptos Narrow Italic.ttf:NarrowItalic" \
              "Aptos Narrow Bold Italic.ttf:NarrowBoldItalic" "Aptos Display.ttf:DisplayRegular" "Aptos Display Bold.ttf:DisplayBold" \
              "Aptos Display Italic.ttf:DisplayItalic" "Aptos Display Bold Italic.ttf:DisplayBoldItalic"; do
    "$PY" -I scripts/extract_metrics.py "$APTOS_DIR/${pair%%:*}" "build/metrics/ref_${pair##*:}.json"
  done
  "$PY" -I scripts/build_sources.py --opensans .opensans/sources --noto .noto --metrics build/metrics \
        --out sources --report build/fit_report.json
}

do_fonts() {
  "$PY" -I scripts/check_locked.py sources/*.ufo || {
    echo "Locked advance widths changed (see above): the build continues, but metric compatibility is broken." >&2; }
  "$PY" -I scripts/build_fonts.py --sources sources --out fonts --build build
}

do_check() {
  need_aptos
  "$PY" -I scripts/check_metrics.py --fonts fonts/ttf --aptos "$APTOS_DIR" --json build/check.json
  "$PY" -I scripts/linebreak.py --fonts fonts/ttf --aptos "$APTOS_DIR" --json build/linebreak.json
}

do_images() {
  need_aptos
  bash scripts/fetch_opensans.sh .opensans
  "$PY" -I scripts/render.py --fonts fonts/ttf --aptos "$APTOS_DIR" --out docs/comparison --images docs/images \
        --opensans-vf ".opensans/fonts/variable/OpenSans[wdth,wght].ttf"
}

case "${1:-fonts}" in
  fit) do_fit ;;
  fonts) do_fonts ;;
  check) do_check ;;
  images) do_images ;;
  all) do_fit; do_fonts; do_check; do_images ;;
  *) echo "usage: $0 {fonts|check|images|fit|all}" >&2; exit 2 ;;
esac
