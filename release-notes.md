# v0.0.23

Distribution-robustness release. No app behavior changes.

- **Notarized, stapled DMG** is now built and published alongside the ZIP
  (`bt-web-report-manager-0.0.23.dmg`). DMG drag-install avoids the
  signature-corruption that third-party unarchivers cause when expanding the
  ZIP, which produced spurious "is damaged and can't be opened" errors.
- **`scripts/install-app.sh`** added: installs a release archive (ZIP or DMG)
  with Apple's `ditto`, verifying signature + notarization before and after
  install. Use this instead of double-clicking the ZIP.
- Release tooling: `build-app.sh` builds + signs + notarizes + staples the DMG;
  `make publish-release` uploads both the ZIP and the DMG.
- See `docs/notarization-preflight.md` for the pre-publish verification gate.
