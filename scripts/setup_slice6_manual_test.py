"""Create an isolated manual acceptance profile for Slice 6."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
MANUAL_ROOT = REPO_ROOT / ".manual" / "slice6"
APP_SUPPORT = MANUAL_ROOT / "app-support"
BIN_DIR = MANUAL_ROOT / "bin"
PROJECTS_ROOT = MANUAL_ROOT / "projects"
VANDAM_PROJECT = Path("/Users/em/Dropbox/bldgtyp/2606 29 Vandam St/04_Web")


def main() -> None:
    if MANUAL_ROOT.exists():
        shutil.rmtree(MANUAL_ROOT)
    APP_SUPPORT.mkdir(parents=True)
    BIN_DIR.mkdir(parents=True)
    PROJECTS_ROOT.mkdir(parents=True)

    btwr_wrapper = BIN_DIR / "btwr-local"
    btwr_wrapper.write_text("#!/bin/sh\n" f"cd {sh_quote(WORKSPACE_ROOT)} || exit 1\n" 'exec uv run btwr "$@"\n')
    btwr_wrapper.chmod(0o755)

    commit_project = _create_commit_push_project()
    settings = {
        "projects_root": str(PROJECTS_ROOT),
        "extra_project_paths": [str(VANDAM_PROJECT)],
        "btwr_executable": str(btwr_wrapper),
        "pnpm_executable": shutil.which("pnpm") or "pnpm",
        "git_executable": shutil.which("git") or "git",
        "gh_executable": shutil.which("gh") or "gh",
        "editor_command": shutil.which("code") or "code",
        "github_owner": "example",
        "github_repo": "bt-web-report-manager",
        "lock_ttl_hours": 4,
    }
    (APP_SUPPORT / "settings.yaml").write_text(yaml.safe_dump(settings, sort_keys=False))
    _write_readme(commit_project, btwr_wrapper)
    print(f"Slice 6 manual profile ready: {MANUAL_ROOT}")
    print(f"Launch with: BTWR_MANAGER_APP_SUPPORT={APP_SUPPORT} uv run btwr-manager")


def _create_commit_push_project() -> Path:
    remote = MANUAL_ROOT / "remotes" / "slice6-commit-push.git"
    project = PROJECTS_ROOT / "Slice 6 Commit Push Manual Test" / "04_Web"
    remote.parent.mkdir(parents=True)
    project.mkdir(parents=True)

    _run(["git", "init", "--bare", str(remote)])
    _run(["git", "init", str(project)])
    _run(["git", "config", "user.email", "test@example.com"], cwd=project)
    _run(["git", "config", "user.name", "Slice 6 Manual Test"], cwd=project)
    _run(["git", "branch", "-M", "main"], cwd=project)
    _run(["git", "remote", "add", "origin", str(remote)], cwd=project)

    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": "slice6-commit-push",
                "project_title": "Slice 6 Commit Push Manual Test",
                "client_name": "Manual QA",
                "phase": "Acceptance",
                "source_files": {"data_dir": "data"},
            },
            sort_keys=False,
        )
    )
    (project / "README.md").write_text("Initial disposable report data.\n")
    _run(["git", "add", "project.yaml", "README.md"], cwd=project)
    _run(["git", "commit", "-m", "Initial"], cwd=project)
    _run(["git", "push", "-u", "origin", "main"], cwd=project)

    (project / "README.md").write_text("Updated disposable report data for Slice 6 acceptance.\n")
    return project


def _write_readme(commit_project: Path, btwr_wrapper: Path) -> None:
    (MANUAL_ROOT / "README.md").write_text(
        "# Slice 6 Manual Acceptance Harness\n\n"
        "This folder is disposable. Re-run `uv run python scripts/setup_slice6_manual_test.py` "
        "from `bt-web-report-manager/` to reset it.\n\n"
        "Launch:\n\n"
        "```sh\n"
        f"BTWR_MANAGER_APP_SUPPORT={APP_SUPPORT} uv run btwr-manager\n"
        "```\n\n"
        "The isolated settings profile includes:\n\n"
        f"- live Vandam: `{VANDAM_PROJECT}`\n"
        f"- disposable commit/push repo: `{commit_project}`\n"
        f"- local btwr wrapper: `{btwr_wrapper}`\n"
    )


def _run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)


def sh_quote(path: Path) -> str:
    return "'" + str(path).replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    main()
