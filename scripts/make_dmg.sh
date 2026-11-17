#!/bin/bash
# Build a .dmg from dist/TrailBuddy Analyzer.app (run after PyInstaller). Usage: scripts/make_dmg.sh [version]
set -euo pipefail
cd "$(dirname "$0")/.."
VER="${1:-$(uv run python -c 'import trailbuddy; print(trailbuddy.__version__)')}"
STAGE="$(mktemp -d)"
cp -R "dist/TrailBuddy Analyzer.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
OUT="dist/TrailBuddy-Analyzer-$VER-macOS-arm64.dmg"
rm -f "$OUT"
hdiutil create -volname "TrailBuddy Analyzer" -srcfolder "$STAGE" -ov -format UDZO "$OUT" >/dev/null
rm -rf "$STAGE"
echo "$OUT"
