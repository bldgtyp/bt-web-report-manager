#!/usr/bin/env bash
# Install (or reinstall) the bt-web-report Manager from a release archive using
# Apple's `ditto`, which preserves the code signature and stapled ticket.
#
# WHY THIS EXISTS: PyInstaller .app bundles contain sealed symlinks and macOS
# metadata (AppleDouble ._ entries). Double-clicking the zip with a third-party
# unarchiver (Keka, The Unarchiver, etc.) or letting a browser auto-expand it
# mangles those resources and invalidates the signature, which macOS reports as
# "is damaged and can't be opened." Extracting with `ditto` does not.
#
# Usage:
#   ./scripts/install-app.sh                 # newest dist/<...>.zip in this repo
#   ./scripts/install-app.sh /path/to.zip    # explicit archive (.zip or .dmg)
#
# For a partner (John) with the shared Dropbox: just run it with no arguments
# from this folder. The synced dist/ zip is used directly -- no download needed.
set -euo pipefail

APP_NAME="bt-web-report Manager"
APP_DEST="/Applications/$APP_NAME.app"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

fail() { echo "ERROR: $*" >&2; exit 1; }

ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
  ARCHIVE="$(ls -t "$REPO_DIR"/dist/bt-web-report-manager-*.zip 2>/dev/null | head -1 || true)"
  [ -n "$ARCHIVE" ] || fail "no release zip found in $REPO_DIR/dist. Pass one explicitly."
fi
[ -f "$ARCHIVE" ] || fail "archive not found: $ARCHIVE"
echo "Source archive: $ARCHIVE"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

case "$ARCHIVE" in
  *.dmg)
    MNT="$TMP/mnt"; mkdir -p "$MNT"
    hdiutil attach -nobrowse -readonly -mountpoint "$MNT" "$ARCHIVE" >/dev/null
    ditto "$MNT/$APP_NAME.app" "$TMP/$APP_NAME.app"
    hdiutil detach "$MNT" >/dev/null
    ;;
  *.zip)
    ditto -x -k "$ARCHIVE" "$TMP"
    ;;
  *)
    fail "unsupported archive type (need .zip or .dmg): $ARCHIVE" ;;
esac

SRC="$TMP/$APP_NAME.app"
[ -d "$SRC" ] || fail "'$APP_NAME.app' not found inside archive"

# Verify BEFORE touching /Applications so a bad archive never replaces a good
# install. A notarized, stapled bundle passes both checks offline.
echo "== verifying extracted bundle =="
codesign --verify --deep --strict --verbose=2 "$SRC" \
  || fail "signature invalid in extracted bundle (archive or extraction is corrupt)"
spctl -a -vvv -t exec "$SRC" \
  || fail "Gatekeeper rejected the bundle (not notarized?)"

[ -d "$APP_DEST" ] && { echo "Removing existing $APP_DEST"; rm -rf "$APP_DEST"; }
echo "Installing to $APP_DEST"
ditto "$SRC" "$APP_DEST"

echo "== verifying installed copy =="
codesign --verify --deep --strict "$APP_DEST" && echo "  SIGNATURE OK"
spctl -a -vvv -t exec "$APP_DEST"
xcrun stapler validate "$APP_DEST" >/dev/null 2>&1 && echo "  STAPLE OK"

echo "Done. Launching $APP_NAME..."
open "$APP_DEST"
