# Notarization pre-flight gate

Short checklist that guarantees a published build opens on a partner Mac
(John's) with **no `xattr` step**. Run this every time, before `make
publish-release`.

Background: see `release-checklist.md` for the full release path. This doc
is only the verification gate. The build tooling already notarizes and
staples correctly — the v0.0.22 "damaged" incident happened because an
**ad-hoc** build (`make build`) was published instead of a notarized one
(`make release-build`). This gate exists to make that mistake impossible to
ship unnoticed.

## The one rule

For anything you publish or hand to a partner, build with:

```bash
make release-build
```

**Never publish the output of plain `make build`** — that path is ad-hoc
signed (`CODESIGN_IDENTITY="-"`), which is exactly what triggers the
"is damaged and can't be opened" Gatekeeper message on a downloaded copy.

`make release-build` supplies the real identity + notarize profile:

- `CODESIGN_IDENTITY = 2D9B3302F8D8203D837B071A3CFAF5CD9FEACF4E` (Developer ID Application)
- `NOTARIZE_PROFILE = bt-web-report-manager`
- Team ID `JPJ3AJ5U8A`, Apple ID `ed.p.may@gmail.com`

If notarization succeeds you'll see the build script print
`Notarized archive: dist/bt-web-report-manager-<version>.zip` and a clean
`spctl` line near the end. If you do **not** see that, stop — the build was
not notarized and must not be published.

## Gate: verify the actual release ZIP

Run this block from `bt-web-report-manager/` after `make release-build` and
**before** `make publish-release`. It checks the zipped artifact John will
download — not the unzipped `dist/` bundle — and it simulates the download
quarantine flag that caused the original failure.

```bash
VERSION=$(uv run python -c "from bt_web_report_manager import __version__ as v; print(v)")
ZIP="dist/bt-web-report-manager-${VERSION}.zip"
TMP="$(mktemp -d)"
ditto -x -k "$ZIP" "$TMP"                       # extract the way the updater/Finder does
APP="$TMP/bt-web-report Manager.app"

echo "== 1. staple ticket present =="
xcrun stapler validate "$APP"

echo "== 2. signature intact =="
codesign --verify --deep --strict --verbose=2 "$APP"
codesign -dvv "$APP" 2>&1 | grep -E "Authority=Developer ID|TeamIdentifier|flags="

echo "== 3. Gatekeeper accepts (clean copy) =="
spctl -a -vvv -t exec "$APP"

echo "== 4. Gatekeeper accepts WITH download quarantine (the real John case) =="
xattr -w com.apple.quarantine "0083;00000000;Safari;$(uuidgen)" "$APP"
spctl -a -vvv -t exec "$APP"

rm -rf "$TMP"
```

### Expected output — all four must pass

| Check | Pass looks like | Fail looks like |
|-------|-----------------|-----------------|
| 1. staple | `The validate action worked!` | `does not have a ticket stapled` / `Error 65` |
| 2. signature | `Authority=Developer ID Application: ... (JPJ3AJ5U8A)`, `TeamIdentifier=JPJ3AJ5U8A`, `flags=0x10000(runtime)` | `TeamIdentifier=not set`, missing `runtime` flag, or `adhoc` |
| 3. spctl clean | `accepted` and `source=Notarized Developer ID` | `rejected`, `source=Unnotarized` |
| 4. spctl quarantined | **still** `accepted` / `source=Notarized Developer ID` | `rejected` → John gets "damaged" |

**Check 4 is the decisive one.** It puts the same `com.apple.quarantine`
flag on the app that a Safari/Firefox download applies, then asks Gatekeeper
to assess it. If this prints `accepted` / `source=Notarized Developer ID`,
John's download will open with a normal first-run prompt and no `xattr`
workaround. If any check fails, do not publish — re-run `make release-build`
and confirm notarization actually completed.

## Gate: verify the DMG too

`make release-build` now also produces a notarized, stapled
`dist/bt-web-report-manager-<version>.dmg` (the drag-install format for
partners). Verify it the same way:

```bash
VERSION=$(uv run python -c "from bt_web_report_manager import __version__ as v; print(v)")
DMG="dist/bt-web-report-manager-${VERSION}.dmg"

echo "== DMG ticket present =="
xcrun stapler validate "$DMG"                         # -> The validate action worked!

echo "== DMG accepted by Gatekeeper =="
spctl -a -vv -t open --context context:primary-signature "$DMG"   # -> accepted / Notarized Developer ID

echo "== app inside the DMG is itself stapled (opens offline once dragged out) =="
MNT="$(mktemp -d)"
hdiutil attach -nobrowse -readonly -mountpoint "$MNT" "$DMG" >/dev/null
xcrun stapler validate "$MNT/bt-web-report Manager.app"
spctl -a -vvv -t exec "$MNT/bt-web-report Manager.app"
hdiutil detach "$MNT" >/dev/null
```

## Then publish

Only after all checks pass:

```bash
make publish-release   # uploads both the .zip and the .dmg
```

## Partner installs: the artifact is not the only failure point

A fully notarized, stapled artifact can **still** show "is damaged and can't
be opened" on a partner's Mac if they extract the ZIP with anything other than
Apple's `ditto` / Archive Utility. PyInstaller bundles carry sealed symlinks
and AppleDouble (`._`) metadata; third-party unarchivers (Keka, The
Unarchiver) and browser auto-expand corrupt them and invalidate the signature.
Telltale sign: removing quarantine with `xattr -dr com.apple.quarantine` does
**not** fix it (a quarantine problem would clear; a broken-signature problem
won't).

Give partners one of these, in order of robustness:

1. **The DMG** — drag-install, nothing to extract, nothing to corrupt. Preferred.
2. **`scripts/install-app.sh`** — extracts with `ditto`, verifies signature +
   notarization before and after install, then launches. Works against the
   synced Dropbox `dist/` zip with no download:
   `./scripts/install-app.sh`.
3. **Manual `ditto`** — `ditto -x -k <zip> /Applications/` (never double-click
   the zip).

## If a build ever fails the gate

1. Confirm you ran `make release-build`, not `make build`.
2. Confirm the notarize profile still exists:
   `xcrun notarytool history --keychain-profile bt-web-report-manager`.
   If missing, recreate it (see `release-checklist.md` → Notarize →
   `store-credentials`).
3. Re-check the submission result:
   `xcrun notarytool log <submission-id> --keychain-profile bt-web-report-manager`
   — Apple lists the exact rejection reason (common: a nested binary not
   signed with the hardened runtime; `build-app.sh` signs `--deep`, so this
   usually means an unsigned dylib pulled in by a new dependency).
4. Never ship the ad-hoc build as a stopgap. If a partner is blocked,
   the `xattr -dr com.apple.quarantine` workaround is the temporary patch —
   not a re-published ad-hoc ZIP.
