#!/usr/bin/env bash
# Download the Noto fonts (SIL OFL 1.1, no Reserved Font Name) that supply the characters Open
# Sans lacks, at a pinned google/fonts commit, into .noto/ (git-ignored; nothing is committed).
#   https://github.com/google/fonts  commit 47d54ca1ebb14fd864695f1d39dc734f39017c33 (2026-10-16)
set -euo pipefail
COMMIT=47d54ca1ebb14fd864695f1d39dc734f39017c33
DEST="${1:-.noto}"
FILES=(
  "notosans/NotoSans[wdth,wght].ttf"
  "notosans/NotoSans-Italic[wdth,wght].ttf"
  "notosansmono/NotoSansMono[wdth,wght].ttf"
  "notosanssymbols/NotoSansSymbols[wght].ttf"
  "notosanssymbols2/NotoSansSymbols2-Regular.ttf"
  "notosansmath/NotoSansMath-Regular.ttf"
  "notosanscoptic/NotoSansCoptic-Regular.ttf"
  "notosansarmenian/NotoSansArmenian[wdth,wght].ttf"
  "notosansarabic/NotoSansArabic[wdth,wght].ttf"
  "notosansbengali/NotoSansBengali[wdth,wght].ttf"
  "notosansgujarati/NotoSansGujarati[wdth,wght].ttf"
  "notosanstamil/NotoSansTamil[wdth,wght].ttf"
  "notosansthai/NotoSansThai[wdth,wght].ttf"
  "notosanskhmer/NotoSansKhmer[wdth,wght].ttf"
)
SUMS='58e6e0ebd1931b29a365aa2d3e2ee9a9e831a3af7cf3ad1462d4e72154f0b291  NotoSans-Italic[wdth,wght].ttf
bfb7bb691513f12e734dc346c03a03f784912432d7e3fa8e56efcf906fe86b3d  NotoSans[wdth,wght].ttf
63111b5b2e074dd48cc67692e0a2726d86ee94c1c37fe8598257b7b4e87e869e  NotoSansArabic[wdth,wght].ttf
0870908d8318435a5daf1cd280ae15063f990cd9ad60f3e94c734ce9e1ffef71  NotoSansArmenian[wdth,wght].ttf
dcd42978094e584a849c84a51450eeac40c8826057d566ea6d4b9627a403a05a  NotoSansBengali[wdth,wght].ttf
51990af1bb0df7be8bfe98fda97769cecfa36eee15381e5504df400276abd735  NotoSansCoptic-Regular.ttf
9901d8552f1dd5d2c50dbd4caa6f6e174e74e8264f06594ab259ae6e7b1ac428  NotoSansGujarati[wdth,wght].ttf
f37a8431a0c5d5ed2f81a767417546aca576a81fb7eff9c924d46aecf828f2ca  NotoSansKhmer[wdth,wght].ttf
3f495fe933c06786e4d5f6d86b8ee70b6753a68ee3b9d87528726de0f6e2c47d  NotoSansMath-Regular.ttf
2cb2adb378a8f574213e23df697050b83c54c27df465a2015552740b2769a081  NotoSansMono[wdth,wght].ttf
f7e7e04b4a24b6c78893d50cbfd2b2f6cae49617ab047bfef668d252adb128f7  NotoSansSymbols[wght].ttf
7d5fb73b7ca67a6798101741f5d280a3d016a56a197afcd4199dbb57b4b82a21  NotoSansSymbols2-Regular.ttf
aa3a9b321f4b0bb2c40203ffbde9af89713227866e0e13f76e5b9eeea727cf88  NotoSansTamil[wdth,wght].ttf
5a1c559bb539583c8a1fd99d1c5b9491e5e14478c9cd2bd0970d5c3096cc9ef8  NotoSansThai[wdth,wght].ttf'
if [ -f "$DEST/.complete" ]; then echo "$DEST already present"; exit 0; fi
mkdir -p "$DEST"
for f in "${FILES[@]}"; do
  curl -gsfL -o "$DEST/$(basename "$f")" "https://raw.githubusercontent.com/google/fonts/$COMMIT/ofl/$f"
done
curl -gsfL -o "$DEST/OFL.txt" "https://raw.githubusercontent.com/google/fonts/$COMMIT/ofl/notosans/OFL.txt"
( cd "$DEST" && printf '%s\n' "$SUMS" | shasum -a 256 -c - )
touch "$DEST/.complete"
echo "Noto fonts at $DEST"
