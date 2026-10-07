#!/usr/bin/env bash
# Install MongolHorizont for the current user and make it the default font
# for traditional Mongolian script (incl. Todo) in all fontconfig-based
# applications (GNOME, LibreOffice, Firefox, Emacs fallback, ...).
#
# Usage: ./install-mongolhorizont.sh [FONT_DIR]
#   FONT_DIR defaults to the directory containing this script.
cd ./build/
set -euo pipefail

SRC_DIR="$(realpath "${1:-$(dirname "$0")}")"
FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/fontconfig/conf.d"
CONF="$CONF_DIR/60-mongolian.conf"
FILES=(MongolHorizont-Regular.ttf MongolHorizont-Italic.ttf)

# Check that both font files exist before touching anything
for f in "${FILES[@]}"; do
    [[ -f "$SRC_DIR/$f" ]] || { echo "Missing: $SRC_DIR/$f" >&2; exit 1; }
done

# 1. Fonts: symlinks with absolute targets
mkdir -p "$FONT_DIR"
for f in "${FILES[@]}"; do
    ln -sfn "$SRC_DIR/$f" "$FONT_DIR/$f"
    echo "Linked $FONT_DIR/$f -> $SRC_DIR/$f"
done

# 2. Fontconfig rules: replaces 60-mongolian.conf (a backup of the old file is kept)
#  - Unifont is removed from the candidates (bitmap last resort, ranks too high);
#  - text tagged mn-cn asks for MongolHorizont first;
#  - for untagged text the Mongolian fonts are appended to the generic families
#    in this order: MongolHorizont, Noto Sans Mongolian, Mongolian Universal White.
#    The binding is weak: with "same" (= strong for the generic names) these fonts
#    would outrank the Latin fonts and take over Latin text as well.
mkdir -p "$CONF_DIR"
rm -f "$CONF_DIR/50-mongolhorizont.conf"           # rule file of an earlier version of this script
if [[ -f $CONF ]]; then
    cp "$CONF" "$CONF.bak.$(date +%Y%m%d%H%M%S)"
    echo "Backed up existing $CONF"
fi
cat > "$CONF" <<'XML'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>

  <!-- Remove the Unifont family from the candidates -->
  <selectfont>
    <rejectfont>
      <pattern><patelt name="family"><string>Unifont</string></patelt></pattern>
    </rejectfont>
    <rejectfont>
      <pattern><patelt name="family"><string>Unifont-JP</string></patelt></pattern>
    </rejectfont>
    <rejectfont>
      <pattern><patelt name="family"><string>Unifont Sample</string></patelt></pattern>
    </rejectfont>
  </selectfont>

  <!-- Explicit language tag mn-cn: MongolHorizont first -->
  <match target="pattern">
    <test name="lang" compare="contains"><string>mn-cn</string></test>
    <edit name="family" mode="prepend" binding="strong">
      <string>MongolHorizont</string>
    </edit>
  </match>

  <!-- Fallback chain of the generic families; order = priority -->
  <alias binding="weak">
    <family>sans-serif</family>
    <accept>
      <family>MongolHorizont</family>
      <family>Noto Sans Mongolian</family>
      <family>Mongolian Universal White</family>
    </accept>
  </alias>
  <alias binding="weak">
    <family>serif</family>
    <accept>
      <family>MongolHorizont</family>
      <family>Noto Sans Mongolian</family>
      <family>Mongolian Universal White</family>
    </accept>
  </alias>
  <alias binding="weak">
    <family>monospace</family>
    <accept>
      <family>MongolHorizont</family>
      <family>Noto Sans Mongolian</family>
      <family>Mongolian Universal White</family>
    </accept>
  </alias>

</fontconfig>
XML
echo "Wrote $CONF"

# Force a rebuild; a plain fc-cache may miss in-place updates of link targets
fc-cache -f "$FONT_DIR"

# 3. Check: which font now renders Mongolian (U+1820) and Latin text
echo
fail=0
for fam in sans-serif serif monospace; do
    mong=$(fc-match -f '%{family[0]}' "$fam:charset=1820")
    latin=$(fc-match -f '%{family[0]}' "$fam")
    printf '%-10s  Mongolian: %-16s Latin: %s\n' "$fam" "$mong" "$latin"
    [[ $mong == MongolHorizont ]] || fail=1
done
[[ $fail == 0 ]] || { echo "MongolHorizont is not the Mongolian default; another config overrides it" >&2; exit 1; }
echo
echo "Done. Restart running applications (Emacs, LibreOffice, Firefox) to apply."
