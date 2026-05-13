# bt-web-report-manager

PySide6 macOS GUI that wraps the `btwr` CLI. Shipped as a DMG via
GitHub Releases with auto-update on launch.

**Standalone venv** — this package is intentionally NOT a member of the
parent uv workspace. It shells out to `btwr` as a subprocess (it never
`import`s from `bt-web-report-cli` or `bt-web-report-schemas`), and its
PySide6 + briefcase toolchain is heavy enough that mixing into the CLI's
venv would be unpleasant.

## Dev quickstart

```bash
cd bt-web-report-manager
uv sync --extra dev
uv run btwr-manager
```

## Checks

```bash
uv run pytest
uv run black --check src tests
uv run mypy src tests
```

The app reads settings from
`~/Library/Application Support/bt-web-report-manager/settings.yaml`.
For tests or local experiments, set `BTWR_MANAGER_APP_SUPPORT` to point at a
temporary folder.

## Current command contract

Phase 5 wraps the existing platform tools instead of importing their
implementation. The CLI already supports the required scrape contract:

```bash
btwr scrape <project_path>
```

The manager also expects `pnpm`, `git`, `gh`, and the configured editor command
to be available, but missing tools should appear as setup warnings rather than
crashing the GUI.

The default `btwr` lookup is intentionally plain `btwr` on `PATH`. In local
workspace development, use Settings to point the manager at the installed CLI
entry point once the CLI package is installed into an environment visible to the
app.

The Scrape, Dev preview, Reveal, Open editor, and Commit & push buttons run
through a Qt process runner and stream output into the action log. Scrape, Dev
preview, and Commit & push write/refresh a Dropbox soft lock before running.
Commit & push only enables for dirty git worktrees and requires a commit message
plus a second confirmation before running `git add -A`, `git commit`, and
`git push`.

On launch, the manager checks GitHub Releases for
`bldgtyp/bt-web-report-manager` in a background thread. Failures are non-blocking
warnings in the action log; newer releases show an update dialog with the release
URL.
