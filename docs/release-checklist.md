# bt-web-report Manager release checklist

This is the manual release path for the Phase 5 macOS DMG. It stays manual
until release ownership is moved into CI. A local Developer ID Application
identity and notarization keychain profile are available:
`Developer ID Application: Edwin May (JPJ3AJ5U8A)` and
`bt-web-report-manager`.

## Build locally

Run from `bt-web-report-manager/`:

```bash
uv sync --extra dev --extra package
uv run black --check src tests scripts
uv run mypy src tests scripts/setup_slice5_manual_test.py scripts/setup_slice6_manual_test.py
uv run pytest
uv run --extra package briefcase create macOS app
uv run --extra package briefcase build macOS app
uv run --extra package briefcase package macOS app -p dmg \
  --identity "Developer ID Application: Edwin May (JPJ3AJ5U8A)"
```

Expected artifacts:

- `.app`: `build/bt_web_report_manager/macos/app/bt-web-report Manager.app`
- DMG: `dist/bt-web-report Manager-<version>.dmg`

If Briefcase reports that source, dependency, icon, or metadata changes are not
reflected, rerun the relevant command with `-u`, `-r`, `--update-resources`, or
rerun `briefcase create` as prompted by Briefcase.

## Signed and notarized local smoke

Use this path before sharing outside Ed's machine:

```bash
open "dist/bt-web-report Manager-0.0.1.dmg"
```

Then:

1. Drag `bt-web-report Manager.app` into `/Applications` or run it from the
   mounted DMG.
2. Launch from Finder, not from the dev shell.
3. Open Settings and set executable paths for `btwr`, `pnpm`, `git`, `gh`, and
   the editor if the packaged app cannot see shell PATH.
4. Confirm Doctor reports settings-folder write access and expected tool paths.
5. Confirm Vandam is discovered from Dropbox with meaningful status badges.
6. Click Check updates and confirm the GitHub Releases check logs success or a
   non-blocking failure.
7. Run a safe Vandam Dev preview smoke and stop it from the GUI.
8. Run Commit & push only against a disposable repo or controlled branch.

The DMG above should be Developer ID signed, notarized, and stapled. Verify it
before sharing:

```bash
spctl -a -t open --context context:primary-signature -vv "dist/bt-web-report Manager-0.0.1.dmg"
stapler validate "dist/bt-web-report Manager-0.0.1.dmg"
hdiutil verify "dist/bt-web-report Manager-0.0.1.dmg"
```

## Signed/notarized release

Use this path before publishing a normal GitHub Release:

1. Confirm the local machine has an Apple Developer ID Application certificate
   for BLDGTYP in Keychain Access.
2. Confirm notarization credentials are available locally:

   ```bash
   xcrun notarytool history --keychain-profile bt-web-report-manager
   ```

3. If notary credentials are not already stored, create a local Keychain profile
   from a terminal prompt:

   ```bash
   xcrun notarytool store-credentials bt-web-report-manager \
     --apple-id "ed.p.may@gmail.com" \
     --team-id "JPJ3AJ5U8A"
   ```

   Enter the app-specific password at the secure prompt. Do not store the
   password in this repo.
4. Run the same checks and Briefcase create/build commands.
5. Package with the Developer ID identity and allow Briefcase to notarize:

   ```bash
   uv run --extra package briefcase package macOS app -p dmg \
     --identity "Developer ID Application: Edwin May (JPJ3AJ5U8A)"
   ```

6. If Briefcase does not automatically notarize from local credentials,
   sign the `.app`, package the DMG, notarize the DMG, staple the ticket, and
   verify with `spctl`.
7. Create a GitHub Release for tag `v<version>` in
   `bldgtyp/bt-web-report-manager`.
8. Upload the DMG with a filename like
   `bt-web-report-manager-<version>.dmg`; the Manager update check prefers the
   first `.dmg` release asset.
9. Install the uploaded DMG on Ed's Mac and confirm Finder launch, update check,
   settings, Doctor, Vandam discovery, Dev preview, and disposable Commit & push.

## CI decision

Do not add a GitHub Actions release workflow until signing and notarization
credentials are intentionally configured for CI. For now, the release owner
builds locally, notarizes locally, and uploads the DMG to GitHub Releases.
