#!/bin/bash
# TrailBuddy Analyzer - macOS setup. Double-click this file in Finder (or run it in Terminal).
# It installs the Python environment inside this folder (.venv), downloads the pose model into ./models,
# creates "TrailBuddy Analyzer.app" in ~/Applications and puts an alias on your Desktop.
# Nothing else on your computer is changed.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
echo "TrailBuddy Analyzer setup in: $REPO"

if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  echo
  echo "This setup needs 'uv' (a Python installer from Astral, https://docs.astral.sh/uv/)."
  read -r -p "Install uv now with Astral's official installer? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  else
    echo "Install uv yourself (see README), then run this script again."; exit 1
  fi
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"

echo "Installing Python packages (first run takes a few minutes)..."
"$UV" sync --frozen
echo "Downloading the pose model (about 9 MB, once)..."
"$UV" run python -c "from trailbuddy.core.pose import model_path; print(model_path('full'))"

APP="$HOME/Applications/TrailBuddy Analyzer.app"
echo "Creating $APP ..."
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$REPO/assets/icon.icns" "$APP/Contents/Resources/icon.icns"
cat > "$APP/Contents/MacOS/TrailBuddy" <<LAUNCH
#!/bin/bash
cd "$REPO"
exec "$REPO/.venv/bin/python" -m trailbuddy "\$@" >> "\$HOME/Library/Logs/TrailBuddyAnalyzer.log" 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/TrailBuddy"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>TrailBuddy Analyzer</string>
  <key>CFBundleDisplayName</key><string>TrailBuddy Analyzer</string>
  <key>CFBundleIdentifier</key><string>edu.classproject.trailbuddy-analyzer</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundleExecutable</key><string>TrailBuddy</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
touch "$APP"

echo "Adding an alias to your Desktop..."
osascript >/dev/null <<OSA || echo "(Could not create the Desktop alias automatically; drag the app from ~/Applications instead.)"
tell application "Finder"
  set appFile to POSIX file "$APP" as alias
  set deskFolder to path to desktop folder
  if exists file "TrailBuddy Analyzer" of deskFolder then delete file "TrailBuddy Analyzer" of deskFolder
  set a to make new alias file at deskFolder to appFile
  set name of a to "TrailBuddy Analyzer"
end tell
OSA

echo
echo "Done. Double-click 'TrailBuddy Analyzer' on your Desktop to start."
echo "If you move this folder, run this script again."
