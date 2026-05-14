"""Subprocess helpers shared by actions and setup checks."""

from __future__ import annotations

import shutil
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bt_web_report_manager.models import ManagerSettings, ProjectStatus, ToolStatus
from bt_web_report_manager.settings import settings_write_status


@dataclass(frozen=True)
class CommandSpec:
    name: str
    args: tuple[str, ...]
    cwd: Path | None = None
    long_running: bool = False
    refresh_on_success: bool = False


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    cwd: Path | None
    returncode: int
    stdout: str
    stderr: str


def run_command(args: Sequence[str], cwd: Path | None = None, timeout: float | None = None) -> CommandResult:
    completed = subprocess.run(args, cwd=cwd, timeout=timeout, text=True, capture_output=True, check=False)
    return CommandResult(tuple(args), cwd, completed.returncode, completed.stdout, completed.stderr)


def tool_status(name: str, executable: str, version_args: Sequence[str] = ("--version",)) -> ToolStatus:
    resolved = shutil.which(executable)
    if resolved is None:
        return ToolStatus(name, executable, None, None, False, f"{executable} not found on PATH")
    try:
        result = run_command([resolved, *version_args], timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolStatus(name, executable, resolved, None, False, str(exc))
    output = (result.stdout or result.stderr).strip().splitlines()
    version = output[0] if output else None
    ok = result.returncode == 0
    message = version or ("ok" if ok else f"exit {result.returncode}")
    return ToolStatus(name, executable, resolved, version, ok, message)


def doctor(settings: ManagerSettings) -> list[ToolStatus]:
    return [
        settings_write_status(),
        tool_status("btwr", settings.btwr_executable, ("doctor",)),
        tool_status("pnpm", settings.pnpm_executable),
        tool_status("git", settings.git_executable),
        tool_status("gh", settings.gh_executable, ("--version",)),
        tool_status("editor", settings.editor_command, ("--version",)),
    ]


def scrape_command(project: ProjectStatus, settings: ManagerSettings) -> CommandSpec:
    return CommandSpec(
        name="Scrape",
        args=(settings.btwr_executable, "scrape", str(project.project_path)),
        cwd=project.project_path,
        refresh_on_success=True,
    )


def dev_preview_command(project: ProjectStatus, settings: ManagerSettings) -> CommandSpec:
    args = [settings.btwr_executable, "preview", str(project.project_path), "--pnpm", settings.pnpm_executable]
    if settings.renderer_source is not None:
        args.extend(["--renderer-source", str(settings.renderer_source)])
    return CommandSpec(
        name="Dev preview",
        args=tuple(args),
        cwd=project.project_path,
        long_running=True,
    )


def reveal_command(project: ProjectStatus) -> CommandSpec:
    return CommandSpec(
        name="Reveal in Finder",
        args=("open", "-R", str(project.project_path)),
        refresh_on_success=False,
    )


def open_editor_command(project: ProjectStatus, settings: ManagerSettings) -> CommandSpec:
    args = [settings.btwr_executable, "editor", str(project.project_path), "--pnpm", settings.pnpm_executable]
    if settings.renderer_source is not None:
        args.extend(["--renderer-source", str(settings.renderer_source)])
    return CommandSpec(
        name="Open editor",
        args=tuple(args),
        cwd=project.project_path,
        long_running=True,
        refresh_on_success=False,
    )


def open_code_editor_command(project: ProjectStatus, settings: ManagerSettings) -> CommandSpec:
    return CommandSpec(
        name="Open code editor",
        args=(settings.editor_command, str(project.project_path)),
        refresh_on_success=False,
    )


def commit_push_command(project: ProjectStatus, settings: ManagerSettings, message: str) -> CommandSpec:
    quoted_message = shlex.quote(message)
    quoted_git = shlex.quote(settings.git_executable)
    script = (
        f"{quoted_git} add -A -- . ':!.bldgtyp/lock.yaml' "
        f"&& {quoted_git} commit -m {quoted_message} "
        f"&& {quoted_git} push"
    )
    return CommandSpec(
        name="Commit & push",
        args=("/bin/sh", "-lc", script),
        cwd=project.project_path,
        refresh_on_success=True,
    )
