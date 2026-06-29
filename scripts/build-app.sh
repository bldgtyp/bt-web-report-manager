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
APP_BUNDLE_ID="com.bldgtyp.bt-web-report-manager"
ICON="resources/icon.icns"
ENTRY="src/bt_web_report_manager/__main__.py"
DIST_DIR="dist"
APP_PATH="$DIST_DIR/$APP_NAME.app"
CODESIGN_IDENTITY="${CODESIGN_IDENTITY:--}"
NOTARIZE_PROFILE="${NOTARIZE_PROFILE:-}"

VERSION=$(uv run python -c "from bt_web_report_manager import __version__; print(__version__)")
ZIP_PATH="$DIST_DIR/bt-web-report-manager-${VERSION}.zip"

set_plist_value() {
  local key="$1"
  local value="$2"
  local plist="$3"
  if /usr/libexec/PlistBuddy -c "Set :$key $value" "$plist" >/dev/null 2>&1; then
    return
  fi
  /usr/libexec/PlistBuddy -c "Add :$key string $value" "$plist"
}

verify_release_zip() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN
  ditto -x -k "$ZIP_PATH" "$tmp_dir"
  codesign --verify --deep --strict --verbose=2 "$tmp_dir/$APP_NAME.app"
  spctl -a -vv "$tmp_dir/$APP_NAME.app"
}

# Build a notarized, stapled drag-install DMG from the already-signed (and,
# when NOTARIZE_PROFILE is set, already-stapled) .app. A DMG is the robust
# partner-distribution format: the user drags an untouched bundle out of a
# read-only image, so there is no extraction step to corrupt the signature.
build_dmg() {
  local dmg_path="$DIST_DIR/bt-web-report-manager-${VERSION}.dmg"
  local staging
  staging="$(mktemp -d)"
  trap 'rm -rf "$staging"' RETURN

  echo "Building DMG..."
  ditto "$APP_PATH" "$staging/$APP_NAME.app"
  ln -s /Applications "$staging/Applications"
  rm -f "$dmg_path"
  hdiutil create -volname "$APP_NAME" -srcfolder "$staging" \
    -fs HFS+ -format UDZO -ov "$dmg_path" >/dev/null

  echo "Signing DMG..."
  codesign --force --timestamp --sign "$CODESIGN_IDENTITY" "$dmg_path"

  if [ -n "$NOTARIZE_PROFILE" ]; then
    echo "Notarizing DMG..."
    xcrun notarytool submit "$dmg_path" \
      --keychain-profile "$NOTARIZE_PROFILE" --wait
    xcrun stapler staple "$dmg_path"
    xcrun stapler validate "$dmg_path"
    spctl -a -vv -t open --context context:primary-signature "$dmg_path"
  fi
  echo "DMG: $dmg_path"
}

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

echo "[2b/5] Stamping bundle metadata..."
set_plist_value "CFBundleIdentifier" "$APP_BUNDLE_ID" "$APP_PATH/Contents/Info.plist"
set_plist_value "CFBundleShortVersionString" "$VERSION" "$APP_PATH/Contents/Info.plist"
set_plist_value "CFBundleVersion" "$VERSION" "$APP_PATH/Contents/Info.plist"

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
  verify_release_zip
  echo "Notarized archive: $ZIP_PATH"
  build_dmg
else
  echo "[4/5] Skipping notarization (set NOTARIZE_PROFILE to enable)"
  echo "[5/5] Skipping staple/zip/dmg"
fi

du -sh "$APP_PATH" | awk '{print "Bundle size:", $1}'
echo "Built: $APP_PATH"
