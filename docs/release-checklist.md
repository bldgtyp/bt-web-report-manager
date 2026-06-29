# bt-web-report Manager release checklist

Manual release path for the macOS bundle. Stays manual until release
ownership is moved into CI. A local Developer ID Application identity and
notarization keychain profile are available:
`2D9B3302F8D8203D837B071A3CFAF5CD9FEACF4E` and
`bt-web-report-manager`.

> **Note (2026-05-13)**: Packaging uses `nicegui-pack` (PyInstaller).
> The release artifact is a zipped `.app` rather than a DMG.
> Bundle size is ~110 MB.

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
2. System Check reports settings-folder write access and all expected tool paths.
   Confirm the trace log path is visible and writable:
   `~/Library/Application Support/bt-web-report-manager/logs/manager-trace.log`.
3. Settings round-trips: change `lock_ttl_hours`, save, reopen, value
   persists.
4. Check updates logs a result against `bldgtyp/bt-web-report-manager`.
   When an update is available, Install and relaunch shows a blocking
   download/verify progress dialog, closes the old window/tab, swaps the
   app, and opens the new version.
5. Vandam Dev preview starts and Stop kills the dev server cleanly.
6. Commit & push only against a disposable repo or controlled branch.
7. Full delete only against a disposable dev project; confirm the modal lists
   local folder, GitHub repo, Cloudflare domain, and Cloudflare Pages project
   before accepting.

## Partner setup: John

For the current internal build, the `.app` is the Manager UI only. It still
wraps external command-line tools, so John's Mac needs the same local
toolchain before project actions are safe.

1. Install the Manager app:
   - Download `bt-web-report-manager-<version>.zip` from the
     `bldgtyp/bt-web-report-manager` GitHub Release.
   - Unzip it and move `bt-web-report Manager.app` to `/Applications`.
   - Open it once.
2. Confirm Dropbox access:
   - Dropbox must sync the shared BLDGTYP project root at
     `~/Dropbox/bldgtyp`.
   - Project folders should keep the standard numbered structure, with report
     projects under `04_Web/`.
3. Install local command-line tools:
   - If `git` is missing, run `xcode-select --install`.
   - Install Homebrew if needed.
   - Run `brew install pnpm gh`.
   - Install VS Code's `code` command from VS Code's Command Palette:
     `Shell Command: Install 'code' command in PATH`.
4. Authenticate GitHub:
   - Run `gh auth login`.
   - John needs access to `bldgtyp/bt-web-report-manager`, platform repos under
     `bldgtyp`, and project repos under `bldgtyp-projects`.
   - Verify with `gh auth status`.
5. Provide the `btwr` CLI:
   - Current internal builds do not bundle `btwr`.
   - If John has the shared dev workspace, run `uv sync` at the
     `bt-web-report/` workspace root, then set Manager Settings
     `btwr executable` to that workspace's `.venv/bin/btwr`.
   - If the workspace path differs from Ed's, John must use his own absolute
     path. Do not copy Ed's `/Users/em/...` value.
   - Future packaging should bundle `btwr` or install it as a managed
     companion tool.
6. Run Manager System Check:
   - All rows should be green before project actions.
   - If `btwr` is missing and the workspace CLI is detected, click
     **Use workspace btwr**, then rerun System Check.
7. Smoke-test with a known project:
   - Click Refresh.
   - Open a known project.
   - Try Reveal in Finder, Dev preview, and Stop first.
   - Only use Commit & push after confirming the repo and branch.

The same steps are available in-app from **System Check -> Setup guide** so
John does not need to find this release checklist during setup.

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

> **Gate first:** before publishing, run the verification block in
> `notarization-preflight.md` against `dist/bt-web-report-manager-<version>.zip`.
> All four checks (staple, signature, `spctl` clean, `spctl` with quarantine)
> must pass. This is what prevents a re-occurrence of the ad-hoc "damaged"
> build reaching a partner Mac.

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

The updater extracts release ZIPs with macOS `ditto`, not Python `zipfile`.
PyInstaller app bundles contain sealed symlinks and macOS metadata; extracting
with `zipfile` mutates those resources and invalidates the code signature.

## CI decision

Do not add a GitHub Actions release workflow yet. Until signing and
notarization credentials are intentionally configured for CI, the release
owner builds locally, notarizes locally, and uploads the zipped `.app` to
GitHub Releases.
