#!/usr/bin/env bash
# Build MongolHorizont Regular and Italic from Noto Sans Mongolian.
# Requires: python3, fonttools (pip install fonttools), curl.
set -euo pipefail
cd "$(dirname "$0")"

SRC=NotoSansMongolian-Regular.ttf
URL=https://raw.githubusercontent.com/google/fonts/main/ofl/notosansmongolian/NotoSansMongolian-Regular.ttf
MODE=2                      # only compress the part above the stem

# Regular: stem centre at 1/3.5 of glyph height, 10 degrees leaning right
REG_RATIO=0.2857142857
REG_SLANT=-10
# Italic: stem centre at 1/3.5 of glyph height, 30 degrees leaning right
ITA_RATIO=0.2857142857
ITA_SLANT=-30

[[ -f $SRC ]] || curl -fsSL -o "$SRC" "$URL"
mkdir -p build

python3 horiz.py "$SRC" build/tmp-regular.ttf "$REG_SLANT" tmp "$REG_RATIO" "$MODE"
python3 horiz.py "$SRC" build/tmp-italic.ttf  "$ITA_SLANT" tmp "$ITA_RATIO" "$MODE"
python3 family.py build/tmp-regular.ttf build/MongolHorizont-Regular.ttf Regular
python3 family.py build/tmp-italic.ttf  build/MongolHorizont-Italic.ttf  Italic
rm build/tmp-*.ttf
echo "Fonts written to $(pwd)/build"
