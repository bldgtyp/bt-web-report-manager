# bt-web-report-manager

NiceGUI desktop dashboard that wraps the `btwr` CLI. Packaged `.app` builds
open a native pywebview window; source runs open a browser tab by default.
The app shells out to `btwr`, `pnpm`, `git`, `gh`, and the configured code
editor — every project action ultimately maps to a subprocess so the manager
stays a thin coordinator over Dropbox-synced project folders.

**Standalone venv** — this package is intentionally NOT a member of the
parent uv workspace. It shells out to `btwr` as a subprocess (it never
`import`s from `bt-web-report-cli` or `bt-web-report-schemas`), so keeping
its NiceGUI + PyInstaller toolchain separate avoids polluting the CLI's
dependency surface.

The manager is pinned to Python `>=3.11,<3.14` because NiceGUI + PyInstaller
wheels are best supported in that range today.

## Dev quickstart

```bash
cd bt-web-report-manager
uv sync --extra dev
uv run btwr-manager
```

The server starts on `http://localhost:8765` by default and opens a browser
tab. To open a native pywebview window instead, set the env var:

```bash
BTWR_MANAGER_NATIVE=1 uv run btwr-manager
```

Native windows enable normal document text selection so visible status, paths,
and command output can be selected and copied with the mouse.

Useful env vars:

| Var                          | Purpose                                          |
|------------------------------|--------------------------------------------------|
| `BTWR_MANAGER_PORT`          | Override the default port (8765)                 |
| `BTWR_MANAGER_NATIVE=1`      | Force a native pywebview window                  |
| `BTWR_MANAGER_NATIVE=0`      | Force a browser tab, even from packaged `.app`   |
| `BTWR_MANAGER_APP_SUPPORT`   | Override `~/Library/Application Support/...` for tests |

## Checks

```bash
uv run pytest
uv run black --check src tests
uv run mypy src tests
```

## Packaging

The packaging story is **PyInstaller via `nicegui-pack`**. The build script handles dep sync,
packing, and ad-hoc codesigning so Gatekeeper lets the bundle open locally:

```bash
uv sync --extra dev --extra package
make build
```

This produces `dist/bt-web-report Manager.app`. Bundle size is ~110 MB.

For a signed/notarized release build, run `make release-build`. It wraps the
Developer ID identity and notarytool profile used for this app. See
`docs/release-checklist.md`.

The app reads settings from
`~/Library/Application Support/bt-web-report-manager/settings.yaml`. For
tests or local experiments, set `BTWR_MANAGER_APP_SUPPORT` to point at a
temporary folder.

## What the manager does

- **Toolbar**: New project (wizard), Refresh, Settings, System Check, Check
  updates. Keyboard shortcuts: ⌘N, ⌘R, ⌘,.
- **Project Index**: the default screen for portfolio scanning, setup, and
  navigation. It shows project metrics plus a dense project list with name,
  slug, client/building, phase, PHPP mtime, manifest mtime, git state, and
  status chips. Workflow actions are intentionally kept off this screen.
- **Project Workspace**: opens from a project row and focuses on one project.
  It shows breadcrumb navigation, project metadata, status chips, files and
  locations, a scoped action log, and project state/status explanations.
- **Action cluster**: grouped Run / Author / Publish / Process in the Project
  Workspace.
  - **Scrape**: `btwr scrape <project>` — writes a Dropbox lock first
  - **Dev preview**: `btwr preview <project>` — long-running, writes a lock
  - **Open editor (TinaCMS)**: `btwr editor <project>` — long-running, writes a
    lock; opens TinaCMS and the live preview when the local Astro URL is ready
  - **Open code editor**: launches the configured editor at the project
    path (e.g. `code`)
  - **Commit & push**: prompts for a message, confirms, then
    `git add -A && git commit -m … && git push`
  - **Reveal in Finder**: `open -R <project>`
  - **Stop**: aborts the running subprocess (SIGTERM, then SIGKILL after 2s)
  - **Copy log**: copies the action log to the clipboard
- **Action log** (right pane, bottom): timestamped stdout/stderr stream
  from the current subprocess.
- **Lock handling**: mutating actions (Scrape, Dev preview, Open editor,
  Commit & push) write a Dropbox-synced soft-lock to
  `<project>/.bldgtyp/lock.yaml` with the configured TTL. The manager
  refreshes its own locks every 60 s and releases them on quit. When
  another user/host holds an active lock, the action prompts for
  confirmation before overwriting it.
- **Update check**: polls `bldgtyp/bt-web-report-manager` GitHub releases
  on startup (250 ms after page load) and via the toolbar. For ZIP releases,
  the `Update available` dialog can download, verify, install, and relaunch
  the packaged app; it also keeps manual release-page and asset buttons.

## Current command contract

```
btwr scrape <project_path>
btwr preview <project_path>
btwr editor <project_path>
git add -A -- . ':!.bldgtyp/lock.yaml' && git commit -m <msg> && git push
git status --branch --porcelain=v2
```

`gh` is invoked only by the New-project wizard's optional bootstrap path
when `btwr new --help` is available. Executable lookup includes the configured
value, the shared Dropbox workspace `.venv/bin`, and standard macOS Homebrew /
VS Code command paths so Finder-launched `.app` builds can resolve the same
tools as terminal launches.

Missing tools surface as warnings in the action log and as System Check
findings rather than crashing the GUI.

## Trace log

The Manager writes a rotating support trace at
`~/Library/Application Support/bt-web-report-manager/logs/manager-trace.log`.
System Check shows this path. The trace records app startup, settings
load/save, executable search paths, System Check rows, project discovery, git
and lock status, New-project picker/default/build steps, command arguments,
process output, and failures.

## Partner setup

For John or another BLDGTYP operator, use **System Check → Setup guide** in
the app. It lists the required install steps: Dropbox project-root access,
Homebrew tools (`pnpm`, `gh`), GitHub auth, VS Code's `code` command, and the
current `btwr` CLI path requirement. The full release-owner checklist is in
`docs/release-checklist.md`.
