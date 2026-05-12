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
uv sync
uv run btwr-manager
```
