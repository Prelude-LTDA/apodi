#!/usr/bin/env bash
# Download the Open Sans sources (SIL OFL 1.1) at a pinned commit into .opensans/
#   https://github.com/googlefonts/opensans  commit bd7e37632246368c60fdcbd374dbf9bad11969b6
#   ("Fix version number to v3.003", 2023-11-16) -- the commit that ships the v3.003 fonts.
set -euo pipefail
COMMIT=bd7e37632246368c60fdcbd374dbf9bad11969b6
DEST="${1:-.opensans}"
if [ -f "$DEST/sources/OpenSans-Roman.designspace" ]; then echo "$DEST already present"; exit 0; fi
mkdir -p "$DEST"
TMP="$(mktemp -d)"
curl -sfL -o "$TMP/opensans.tar.gz" "https://codeload.github.com/googlefonts/opensans/tar.gz/$COMMIT"
tar -xzf "$TMP/opensans.tar.gz" -C "$DEST" --strip-components=1 \
  "opensans-$COMMIT/sources" "opensans-$COMMIT/OFL.txt" "opensans-$COMMIT/fonts/variable"
rm -rf "$TMP"
# integrity of the files the build reads directly
( cd "$DEST/sources" && shasum -a 256 -c - <<'SUMS'
8a553ebc9d3909428e0212e9e701010619c863f588264717605e4c10bd5aa6ce  OpenSans-Roman.designspace
ba252da1c92769174067dce18a2169d3bef0d9076eed21b39e27f5b55d0b1424  OpenSans-Italic.designspace
d93795f8851c186e9b82f5c58e4b86f467eabdb7e8bab6be58770209968580ef  OpenSans-glyphset.txt
ea7f25ab2f363cdf7aa7da1f8ee5b84c2815f584a9e12104c0546590b570136f  OpenSans-Regular.ufo/fontinfo.plist
SUMS
)
echo "Open Sans sources at $DEST/sources"
