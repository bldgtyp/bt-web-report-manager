# bt-web-report Manager release checklist

Manual release path for the macOS bundle. Stays manual until release
ownership is moved into CI. A local Developer ID Application identity and
notarization keychain profile are available:
`Developer ID Application: Edwin May (JPJ3AJ5U8A)` and
`bt-web-report-manager`.

> **Note (2026-05-13)**: Packaging switched from Briefcase + DMG to
> `nicegui-pack` (PyInstaller). The release artifact is a zipped `.app`
> rather than a DMG. Bundle size dropped from ~500 MB to ~110 MB.

## Build locally

Run from `bt-web-report-manager/`:

```bash
uv sync --extra dev --extra package
make test
make build
```

For release builds, use the checked-in wrapper so the Developer ID,
notarization profile, ZIP archive, and bundle version metadata are handled
the same way each time:

```bash
make release-build
```

Expected artifacts: `dist/bt-web-report Manager.app` and
`dist/bt-web-report-manager-<version>.zip`.

## Local smoke

Before sharing, run the bundle from `/Applications/`:

```bash
cp -R "dist/bt-web-report Manager.app" /Applications/
open "/Applications/bt-web-report Manager.app"
```

Then exercise:

1. App opens (browser tab or `BTWR_MANAGER_NATIVE=1` window) and projects
   list populates from Dropbox.
2. Doctor reports settings-folder write access and all expected tool paths.
3. Settings round-trips: change `lock_ttl_hours`, save, reopen, value
   persists.
4. Check updates logs a result against `bldgtyp/bt-web-report-manager`.
5. Vandam Dev preview starts and Stop kills the dev server cleanly.
6. Commit & push only against a disposable repo or controlled branch.

## Notarize

```bash
VERSION=$(uv run python -c "from bt_web_report_manager import __version__ as v; print(v)")

# Zip the app for upload
ditto -c -k --keepParent "dist/bt-web-report Manager.app" \
  "dist/bt-web-report-manager-${VERSION}.zip"

# Submit for notarization (uses the stored keychain profile)
xcrun notarytool submit "dist/bt-web-report-manager-${VERSION}.zip" \
  --keychain-profile bt-web-report-manager \
  --wait

# Staple after success and re-zip with the staple
xcrun stapler staple "dist/bt-web-report Manager.app"
rm "dist/bt-web-report-manager-${VERSION}.zip"
ditto -c -k --keepParent "dist/bt-web-report Manager.app" \
  "dist/bt-web-report-manager-${VERSION}.zip"
```

If the notarization profile is not yet stored:

```bash
xcrun notarytool store-credentials bt-web-report-manager \
  --apple-id "ed.p.may@gmail.com" \
  --team-id "JPJ3AJ5U8A"
```

## Publish

```bash
gh release create "v${VERSION}" \
  "dist/bt-web-report-manager-${VERSION}.zip" \
  --title "v${VERSION}" \
  --notes-file release-notes.md
```

Equivalent wrapper:

```bash
make publish-release
```

The wrapper uses `release-notes.md` when present and falls back to GitHub's
generated notes when it is absent.

The asset name pattern `bt-web-report-manager-<version>.zip` is what the
in-app update dialog's install path looks for. The app downloads the ZIP,
extracts the `.app`, verifies code signing / Team ID / Gatekeeper acceptance,
starts a detached helper, quits, swaps the app bundle, and relaunches.

## CI decision

Do not add a GitHub Actions release workflow yet. Until signing and
notarization credentials are intentionally configured for CI, the release
owner builds locally, notarizes locally, and uploads the zipped `.app` to
GitHub Releases.
