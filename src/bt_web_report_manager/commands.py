"""Subprocess helpers shared by actions and setup checks."""

from __future__ import annotations

import os
import shutil
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bt_web_report_manager.models import ManagerSettings, ProjectStatus, ToolStatus
from bt_web_report_manager.settings import (
    app_support_dir,
    settings_write_status,
    workspace_btwr_executable,
    workspace_root_candidates,
)
from bt_web_report_manager.trace import trace_event, trace_exception

EXTRA_EXECUTABLE_DIRS = (
    str(Path("~/.local/bin").expanduser()),
    str(Path("~/bin").expanduser()),
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
    "/Applications/Visual Studio Code.app/Contents/Resources/app/bin",
)

_LOGIN_SHELL_PATH_CACHE: tuple[str, ...] | None = None


def login_shell_path_dirs() -> tuple[str, ...]:
    """Return PATH entries from the user's login shell (cached).

    macOS Finder-launched .app bundles do NOT inherit the user's interactive
    shell PATH, so things in ``~/.zshrc`` / ``~/.zprofile`` are invisible.
    We invoke the login shell once at startup to capture its PATH and merge
    it into ``executable_search_paths()``.
    """
    global _LOGIN_SHELL_PATH_CACHE
    if _LOGIN_SHELL_PATH_CACHE is not None:
        return _LOGIN_SHELL_PATH_CACHE
    shell = os.environ.get("SHELL") or "/bin/zsh"
    try:
        result = subprocess.run(
            [shell, "-l", "-i", "-c", 'printf %s "$PATH"'],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        raw = (result.stdout or "").strip()
        dirs = tuple(p for p in raw.split(os.pathsep) if p)
        trace_event("commands.login_shell_path.captured", shell=shell, dir_count=len(dirs))
    except (OSError, subprocess.SubprocessError) as exc:
        trace_event("commands.login_shell_path.failed", shell=shell, error=str(exc))
        dirs = ()
    _LOGIN_SHELL_PATH_CACHE = dirs
    return dirs


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


def executable_search_path() -> str:
    return os.pathsep.join(executable_search_paths())


def executable_search_paths() -> tuple[str, ...]:
    paths: list[str] = []
    workspace_btwr = workspace_btwr_executable()
    if workspace_btwr is not None:
        paths.append(str(Path(workspace_btwr).parent))
    paths.extend(str(path) for path in renderer_bin_dirs())
    paths.extend(str(path) for path in node_toolchain_bin_dirs())
    paths.extend(path for path in os.environ.get("PATH", "").split(os.pathsep) if path)
    paths.extend(login_shell_path_dirs())
    paths.extend(EXTRA_EXECUTABLE_DIRS)
    unique_paths = tuple(dict.fromkeys(paths))
    trace_event("commands.executable_search_paths", paths=unique_paths)
    return unique_paths


def renderer_bin_dirs() -> tuple[Path, ...]:
    """Return Node executable folders owned by the shared renderer runtime."""
    app_support_renderer_bin = app_support_dir() / "renderer" / "current" / "node_modules" / ".bin"
    workspace_bins = tuple(
        workspace_root / "bt-web-report-template" / "node_modules" / ".bin"
        for workspace_root in workspace_root_candidates()
    )
    return tuple(dict.fromkeys((app_support_renderer_bin, *workspace_bins)))


def node_toolchain_bin_dirs() -> tuple[Path, ...]:
    """Return user-managed Node bins so Finder-launched subprocesses avoid stale system Node."""
    nvm_versions = Path("~/.nvm/versions/node").expanduser()
    if not nvm_versions.exists():
        return ()
    candidates = sorted(nvm_versions.glob("v*/bin"), reverse=True)
    return tuple(path for path in candidates if (path / "node").exists())


def resolve_executable(executable: str) -> str | None:
    executable = executable.strip()
    if not executable:
        trace_event("commands.resolve_executable.empty")
        return None
    expanded = Path(executable).expanduser()
    if expanded != Path(expanded.name):
        ok = expanded.exists() and os.access(expanded, os.X_OK)
        trace_event(
            "commands.resolve_executable.explicit",
            executable=executable,
            expanded=expanded,
            exists=expanded.exists(),
            executable_ok=ok,
        )
        return str(expanded) if ok else None
    search_paths = executable_search_paths()
    for directory in search_paths:
        candidate = Path(directory) / executable
        trace_event(
            "commands.resolve_executable.candidate",
            executable=executable,
            candidate=candidate,
            exists=candidate.exists(),
            executable_ok=os.access(candidate, os.X_OK),
        )
    resolved = shutil.which(executable, path=os.pathsep.join(search_paths))
    trace_event("commands.resolve_executable.result", executable=executable, resolved=resolved)
    return resolved


def command_executable(executable: str) -> str:
    resolved = resolve_executable(executable)
    command = resolved or executable
    trace_event("commands.command_executable", requested=executable, command=command, resolved=resolved is not None)
    return command


def run_command(args: Sequence[str], cwd: Path | None = None, timeout: float | None = None) -> CommandResult:
    env = os.environ.copy()
    env["PATH"] = executable_search_path()
    trace_event("commands.run.start", args=tuple(args), cwd=cwd, timeout=timeout, path=env["PATH"])
    completed = subprocess.run(args, cwd=cwd, env=env, timeout=timeout, text=True, capture_output=True, check=False)
    result = CommandResult(tuple(args), cwd, completed.returncode, completed.stdout, completed.stderr)
    trace_event(
        "commands.run.done",
        args=result.args,
        cwd=result.cwd,
        returncode=result.returncode,
        stdout_preview=result.stdout[-4000:],
        stderr_preview=result.stderr[-4000:],
    )
    return result


def tool_status(name: str, executable: str, version_args: Sequence[str] = ("--version",)) -> ToolStatus:
    trace_event("commands.tool_status.start", name=name, executable=executable, version_args=tuple(version_args))
    resolved = resolve_executable(executable)
    if resolved is None:
        trace_event("commands.tool_status.missing", name=name, executable=executable)
        return ToolStatus(name, executable, None, None, False, f"{executable} not found on Manager PATH")
    try:
        result = run_command([resolved, *version_args], timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        trace_exception("commands.tool_status.exception", exc, name=name, executable=executable, resolved=resolved)
        return ToolStatus(name, executable, resolved, None, False, str(exc))
    output = (result.stdout or result.stderr).strip().splitlines()
    version = output[0] if output else None
    ok = result.returncode == 0
    message = version or ("ok" if ok else f"exit {result.returncode}")
    trace_event(
        "commands.tool_status.done", name=name, executable=executable, resolved=resolved, ok=ok, message=message
    )
    return ToolStatus(name, executable, resolved, version, ok, message)


def doctor(settings: ManagerSettings) -> list[ToolStatus]:
    trace_event("commands.doctor.start", settings=settings)
    statuses = [
        settings_write_status(),
        tool_status("btwr", settings.btwr_executable, ("doctor",)),
        tool_status("pnpm", settings.pnpm_executable),
        tool_status("wrangler", "wrangler"),
        tool_status("git", settings.git_executable),
        tool_status("gh", settings.gh_executable, ("--version",)),
        tool_status("editor", settings.editor_command, ("--version",)),
    ]
    trace_event(
        "commands.doctor.done",
        statuses=[
            {"name": status.name, "ok": status.ok, "executable": status.executable, "path": status.path}
            for status in statuses
        ],
    )
    return statuses


def scrape_command(project: ProjectStatus, settings: ManagerSettings) -> CommandSpec:
    return CommandSpec(
        name="Scrape",
        args=(command_executable(settings.btwr_executable), "scrape", str(project.project_path)),
        cwd=project.project_path,
        refresh_on_success=True,
    )


def dev_preview_command(project: ProjectStatus, settings: ManagerSettings) -> CommandSpec:
    args = [
        command_executable(settings.btwr_executable),
        "preview",
        str(project.project_path),
        "--pnpm",
        command_executable(settings.pnpm_executable),
    ]
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
    args = [
        command_executable(settings.btwr_executable),
        "editor",
        str(project.project_path),
        "--pnpm",
        command_executable(settings.pnpm_executable),
    ]
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
        args=(command_executable(settings.editor_command), str(project.project_path)),
        refresh_on_success=False,
    )


def pull_rebase_command(project: ProjectStatus, settings: ManagerSettings) -> CommandSpec:
    quoted_git = shlex.quote(command_executable(settings.git_executable))
    return CommandSpec(
        name="Pull",
        args=("/bin/sh", "-lc", _git_fetch_rebase_active_branch_script(quoted_git)),
        cwd=project.project_path,
        refresh_on_success=True,
    )


def commit_push_command(project: ProjectStatus, settings: ManagerSettings, message: str) -> CommandSpec:
    quoted_message = shlex.quote(message)
    quoted_git = shlex.quote(command_executable(settings.git_executable))
    script = (
        f"{_git_fetch_rebase_active_branch_script(quoted_git)} "
        f"&& "
        f"{quoted_git} add -A -- . "
        f"&& if {quoted_git} diff --cached --quiet; then "
        f"echo 'No project changes to commit.'; "
        f"else {quoted_git} commit -m {quoted_message}; fi "
        f'&& {quoted_git} push -u origin HEAD:"$branch"'
    )
    return CommandSpec(
        name="Commit & push",
        args=("/bin/sh", "-lc", script),
        cwd=project.project_path,
        refresh_on_success=True,
    )


def _git_fetch_rebase_active_branch_script(quoted_git: str) -> str:
    return (
        f"{quoted_git} remote get-url origin >/dev/null "
        f"&& branch=$({quoted_git} branch --show-current) "
        f'&& if [ -z "$branch" ]; then '
        f"echo 'Git sync requires a named branch, not detached HEAD.'; exit 1; fi "
        f'&& if {quoted_git} ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then '
        f'{quoted_git} fetch origin "$branch:refs/remotes/origin/$branch" '
        f'&& {quoted_git} rebase --autostash "origin/$branch"; '
        f'else echo "No origin/$branch yet; nothing to pull."; fi'
    )


SYNC_PER_PROJECT_DEPRECATION_MESSAGE = (
    "Bulk per-project workflow sync has been removed.\n\n"
    "Per-project repos are no longer mass-rewritten from the template's main "
    "branch — that mechanism allowed any template push to cascade into a "
    "redeploy of every live project (see context/plans/2026-05-23/"
    "renderer-deploy-architecture-restructure-plan.html).\n\n"
    "Replacements:\n"
    "  • Phase 1: `btwr pin <project> --renderer <sha> --schemas <sha>`\n"
    "      Rewrites a single project's workflows to explicit SHAs.\n"
    "  • Phase 5 (in progress): `btwr re-seed <project> --from <sha>`\n"
    "      Updates a project's vendored renderer to a new template ref."
)


def sync_per_project_workflows_command(settings: ManagerSettings) -> CommandSpec | None:
    """Deprecated. Returns None; callers must surface the deprecation message.

    The previous implementation pushed force-rewritten workflows to every repo
    in ``bldgtyp-projects`` from a single bulk action. That coupling is what
    Option C's cascade-stop fixes; see ``SYNC_PER_PROJECT_DEPRECATION_MESSAGE``
    for the replacement workflow.
    """

    return None
