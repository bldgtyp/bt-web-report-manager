"""Create disposable projects for manual Slice 5 subprocess-runner testing."""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANUAL_ROOT = ROOT / ".manual" / "slice5"
PROJECTS_ROOT = MANUAL_ROOT / "projects"
APP_SUPPORT = MANUAL_ROOT / "app-support"
BIN_DIR = MANUAL_ROOT / "bin"


def main() -> None:
    if MANUAL_ROOT.exists():
        shutil.rmtree(MANUAL_ROOT)
    BIN_DIR.mkdir(parents=True)
    APP_SUPPORT.mkdir(parents=True)
    PROJECTS_ROOT.mkdir(parents=True)

    fake_pnpm = _write_fake_pnpm()
    _make_dev_project()
    _make_commit_project()
    _write_settings(fake_pnpm)
    _write_readme()

    print(f"Manual Slice 5 workspace: {MANUAL_ROOT}")
    print("")
    print("Launch the Manager with:")
    print(f"BTWR_MANAGER_APP_SUPPORT={APP_SUPPORT} uv run btwr-manager")
    print("")
    print(f"Test notes: {MANUAL_ROOT / 'README.md'}")


def _write_fake_pnpm() -> Path:
    path = BIN_DIR / "fake-pnpm"
    path.write_text("""#!/bin/sh
if [ "$1" != "dev" ]; then
  echo "fake-pnpm only supports: dev" >&2
  exit 2
fi

echo "fake pnpm dev starting in $(pwd)"
echo "Local: http://localhost:4321/"

i=0
trap 'echo "fake pnpm dev received TERM"; exit 143' TERM INT
while true; do
  i=$((i + 1))
  echo "fake dev heartbeat $i"
  sleep 1
done
""")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _make_dev_project() -> None:
    project = PROJECTS_ROOT / "Slice 5 Dev Server Manual Test" / "04_Web"
    project.mkdir(parents=True)
    _run(["git", "init", str(project)])
    _run(["git", "config", "user.email", "manual-slice5@example.com"], cwd=project)
    _run(["git", "config", "user.name", "Manual Slice 5"], cwd=project)
    _run(["git", "branch", "-M", "main"], cwd=project)
    _write_project_yaml(
        project,
        slug="slice5-dev-server",
        title="Slice 5 Dev Server Manual Test",
        phase="Manual QA",
    )
    _run(["git", "add", "project.yaml"], cwd=project)
    _run(["git", "commit", "-m", "Initial manual dev-server fixture"], cwd=project)


def _make_commit_project() -> None:
    remote = MANUAL_ROOT / "remotes" / "slice5-commit.git"
    project = PROJECTS_ROOT / "Slice 5 Commit Push Manual Test" / "04_Web"
    _run(["git", "init", "--bare", str(remote)])
    _run(["git", "init", str(project)])
    _run(["git", "config", "user.email", "manual-slice5@example.com"], cwd=project)
    _run(["git", "config", "user.name", "Manual Slice 5"], cwd=project)
    _run(["git", "branch", "-M", "main"], cwd=project)
    _run(["git", "remote", "add", "origin", str(remote)], cwd=project)

    _write_project_yaml(
        project,
        slug="slice5-commit-push",
        title="Slice 5 Commit Push Manual Test",
        phase="Manual QA",
    )
    (project / "README.md").write_text("Initial manual Slice 5 commit/push fixture.\n")
    _run(["git", "add", "project.yaml", "README.md"], cwd=project)
    _run(["git", "commit", "-m", "Initial manual fixture"], cwd=project)
    _run(["git", "push", "-u", "origin", "main"], cwd=project)

    hook = remote / "hooks" / "pre-receive"
    hook.write_text("""#!/bin/sh
echo "manual Slice 5 pre-receive hook sleeping; click Stop in Manager now" >&2
sleep 20
cat >/dev/null
exit 0
""")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (project / "README.md").write_text("Dirty manual Slice 5 commit/push fixture.\n")


def _write_project_yaml(project: Path, *, slug: str, title: str, phase: str) -> None:
    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": slug,
                "project_title": title,
                "client_name": "BLDGTYP Internal",
                "phase": phase,
                "source_files": {"data_dir": "data"},
                "publishing": {"production_url": f"https://{slug}.example.test"},
            },
            sort_keys=False,
        )
    )


def _write_settings(fake_pnpm: Path) -> None:
    (APP_SUPPORT / "settings.yaml").write_text(
        yaml.safe_dump(
            {
                "projects_root": str(PROJECTS_ROOT),
                "extra_project_paths": [],
                "btwr_executable": "btwr",
                "pnpm_executable": str(fake_pnpm),
                "git_executable": "git",
                "gh_executable": "gh",
                "editor_command": "open",
                "github_owner": "example",
                "github_repo": "bt-web-report-manager",
                "lock_ttl_hours": 4,
            },
            sort_keys=False,
        )
    )


def _write_readme() -> None:
    (MANUAL_ROOT / "README.md").write_text(f"""# Slice 5 Manual Test Harness

This folder is disposable. Re-run `uv run python scripts/setup_slice5_manual_test.py`
from `bt-web-report-manager/` to reset it.

Launch:

```sh
BTWR_MANAGER_APP_SUPPORT={APP_SUPPORT} uv run btwr-manager
```

## Test A - Dev Preview Stop

1. Select `Slice 5 Dev Server Manual Test`.
2. Click `Dev preview`.
3. Confirm the log shows timestamped rows, including `fake pnpm dev starting`,
   `Local: http://localhost:4321/`, and heartbeat rows.
4. Click `Stop`.
5. Expected: the UI stays responsive, Stop disables after the process exits, and
   the log ends with `Dev preview stopped by user.`

## Test B - Commit & Push Stop

1. Select `Slice 5 Commit Push Manual Test`.
2. Confirm the Git detail shows a dirty worktree.
3. Click `Commit & push`.
4. Accept the suggested commit message and confirm the warning.
5. When the log shows `manual Slice 5 pre-receive hook sleeping`, click `Stop`.
6. Expected: the UI stays responsive and the log ends with
   `Commit & push stopped by user.`

The disposable repo may now have a local commit that did not push. Reset the
harness by re-running the setup script before repeating Test B.
""")


def _run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


if __name__ == "__main__":
    main()
