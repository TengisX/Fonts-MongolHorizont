#!/usr/bin/env bash
# Install MongolHorizont fonts for the current user by symlinking them
# into ~/.local/share/fonts, then rebuild the fontconfig cache.
#
# Usage: ./install-mongolhorizont.sh [FONT_DIR]
#   FONT_DIR defaults to the directory containing this script.
set -euo pipefail

SRC_DIR="$(realpath "${1:-$(dirname "$0")}")"
DEST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"
FILES=(MongolHorizont-Regular.ttf MongolHorizont-Italic.ttf)

# Check that both font files exist before touching anything
for f in "${FILES[@]}"; do
    [[ -f "$SRC_DIR/$f" ]] || { echo "Missing: $SRC_DIR/$f" >&2; exit 1; }
done

mkdir -p "$DEST_DIR"

# Create or replace symlinks with absolute targets
for f in "${FILES[@]}"; do
    ln -sfn "$SRC_DIR/$f" "$DEST_DIR/$f"
    echo "Linked $DEST_DIR/$f -> $SRC_DIR/$f"
done

# Force a rebuild; a plain fc-cache may miss in-place updates of link targets
fc-cache -f "$DEST_DIR"

echo
fc-list : family style | grep -i MongolHorizont || {
    echo "MongolHorizont not found by fontconfig" >&2; exit 1; }
echo
echo "Done. Restart Emacs to pick up the fonts."
