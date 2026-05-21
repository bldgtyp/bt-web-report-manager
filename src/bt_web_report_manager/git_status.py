"""Read-only git status helpers."""

from __future__ import annotations

import re
from pathlib import Path

from bt_web_report_manager.commands import run_command
from bt_web_report_manager.models import GitStatus
from bt_web_report_manager.trace import trace_event

BRANCH_RE = re.compile(r"# branch\.head (?P<branch>.+)")
AB_RE = re.compile(r"# branch\.ab \+(?P<ahead>\d+) -(?P<behind>\d+)")


def read_git_status(project_path: Path, git_executable: str = "git") -> GitStatus:
    trace_event("git.status.start", project_path=project_path, git_executable=git_executable)
    if not (project_path / ".git").exists():
        inside = run_command([git_executable, "rev-parse", "--is-inside-work-tree"], cwd=project_path, timeout=5)
        if inside.returncode != 0:
            trace_event("git.status.not_repo", project_path=project_path, returncode=inside.returncode)
            return GitStatus(is_repo=False)

    status = run_command(
        [git_executable, "status", "--branch", "--porcelain=v2", "--", ".", ":!.bldgtyp/lock.yaml"],
        cwd=project_path,
        timeout=10,
    )
    if status.returncode != 0:
        trace_event("git.status.failed", project_path=project_path, returncode=status.returncode)
        return GitStatus(is_repo=False)

    branch: str | None = None
    ahead = 0
    behind = 0
    dirty_count = 0
    for line in status.stdout.splitlines():
        if match := BRANCH_RE.match(line):
            branch = match.group("branch")
        elif match := AB_RE.match(line):
            ahead = int(match.group("ahead"))
            behind = int(match.group("behind"))
        elif line and not line.startswith("#"):
            dirty_count += 1

    remote_result = run_command([git_executable, "remote", "get-url", "origin"], cwd=project_path, timeout=5)
    remote = remote_result.stdout.strip() if remote_result.returncode == 0 else None
    commit_result = run_command([git_executable, "log", "-1", "--pretty=%h %s"], cwd=project_path, timeout=5)
    last_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None
    git_status = GitStatus(True, branch, dirty_count, ahead, behind, remote, last_commit)
    trace_event("git.status.done", project_path=project_path, status=git_status)
    return git_status
