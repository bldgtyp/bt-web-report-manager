#!/usr/bin/env bash
# Build, sign, optionally notarize and staple the bt-web-report Manager .app.
#
# Usage:
#   ./scripts/build-app.sh                    # ad-hoc sign only (local dev)
#   CODESIGN_IDENTITY="<hash or name>" \
#   NOTARIZE_PROFILE=bt-web-report-manager \
#     ./scripts/build-app.sh                  # full Developer ID + notarize + staple
#
# Env vars:
#   CODESIGN_IDENTITY   "-" (default) for ad-hoc, or a SHA-1 hash / common name
#                       of a Developer ID Application identity.
#   NOTARIZE_PROFILE    Name of a stored notarytool keychain profile. When set,
#                       the script zips, submits, waits, staples, and re-zips.
#
# Requires: uv sync --extra dev --extra package
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="bt-web-report Manager"
ICON="resources/icon.icns"
ENTRY="src/bt_web_report_manager/__main__.py"
DIST_DIR="dist"
APP_PATH="$DIST_DIR/$APP_NAME.app"
CODESIGN_IDENTITY="${CODESIGN_IDENTITY:--}"
NOTARIZE_PROFILE="${NOTARIZE_PROFILE:-}"

VERSION=$(uv run python -c "from bt_web_report_manager import __version__; print(__version__)")
ZIP_PATH="$DIST_DIR/bt-web-report-manager-${VERSION}.zip"

echo "[1/5] Syncing dependencies..."
uv sync --extra dev --extra package

echo "[2/5] Packing with nicegui-pack..."
rm -rf "$APP_PATH" "$DIST_DIR/$APP_NAME" build/
uv run nicegui-pack \
  --onedir \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON" \
  "$ENTRY"

if [ ! -d "$APP_PATH" ]; then
  echo "ERROR: nicegui-pack did not produce $APP_PATH" >&2
  exit 1
fi

if [ "$CODESIGN_IDENTITY" = "-" ]; then
  echo "[3/5] Ad-hoc signing..."
  codesign --force --deep --sign - "$APP_PATH"
else
  echo "[3/5] Signing with Developer ID + hardened runtime..."
  # Hardened runtime is required for notarization. The deep flag walks the
  # bundle and signs nested executables / dylibs with the same options.
  codesign --force --deep --timestamp --options=runtime \
    --sign "$CODESIGN_IDENTITY" "$APP_PATH"
fi

if [ -n "$NOTARIZE_PROFILE" ]; then
  echo "[4/5] Notarizing via keychain profile '$NOTARIZE_PROFILE'..."
  rm -f "$ZIP_PATH"
  ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
  xcrun notarytool submit "$ZIP_PATH" \
    --keychain-profile "$NOTARIZE_PROFILE" \
    --wait

  echo "[5/5] Stapling ticket and re-zipping..."
  xcrun stapler staple "$APP_PATH"
  xcrun stapler validate "$APP_PATH"
  rm -f "$ZIP_PATH"
  ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
  echo "Notarized archive: $ZIP_PATH"
else
  echo "[4/5] Skipping notarization (set NOTARIZE_PROFILE to enable)"
  echo "[5/5] Skipping staple/zip"
fi

du -sh "$APP_PATH" | awk '{print "Bundle size:", $1}'
echo "Built: $APP_PATH"
