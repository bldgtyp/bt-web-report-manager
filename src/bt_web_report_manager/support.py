"""Support diagnostics for brittle local setup paths."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from bt_web_report_manager import __version__
from bt_web_report_manager.commands import resolve_executable, run_command, tool_status
from bt_web_report_manager.models import ManagerSettings, ToolStatus
from bt_web_report_manager.settings import settings_write_status
from bt_web_report_manager.trace import trace_event, trace_log_path


def system_statuses(settings: ManagerSettings) -> list[ToolStatus]:
    """Return setup checks broad enough for support triage."""
    trace_event("support.system_statuses.start", settings=settings)
    statuses = [
        settings_write_status(),
        path_status("projects_root", settings.projects_root, require_dir=True, writable=False),
        renderer_status(settings.renderer_source),
        tool_status("btwr", settings.btwr_executable, ("doctor",)),
        tool_status("pnpm", settings.pnpm_executable),
        tool_status("node", "node"),
        tool_status("wrangler", "wrangler"),
        python_status(),
        tool_status("uv", "uv"),
        tool_status("git", settings.git_executable),
        tool_status("gh", settings.gh_executable, ("--version",)),
        gh_auth_status(settings),
        tool_status("editor", settings.editor_command, ("--version",)),
    ]
    trace_event(
        "support.system_statuses.done",
        statuses=[
            {"name": status.name, "ok": status.ok, "executable": status.executable, "path": status.path}
            for status in statuses
        ],
    )
    return statuses


def path_status(name: str, path: Path, *, require_dir: bool, writable: bool) -> ToolStatus:
    resolved = path.expanduser()
    trace_event("support.path_status.start", name=name, path=resolved, require_dir=require_dir, writable=writable)
    if not resolved.exists():
        return ToolStatus(name, str(path), None, None, False, f"{resolved} does not exist")
    if require_dir and not resolved.is_dir():
        return ToolStatus(name, str(path), str(resolved), None, False, f"{resolved} is not a folder")
    if writable and not os.access(resolved, os.W_OK):
        return ToolStatus(name, str(path), str(resolved), None, False, f"{resolved} is not writable")
    message = "folder exists" if resolved.is_dir() else "path exists"
    return ToolStatus(name, str(path), str(resolved), None, True, message)


def python_status() -> ToolStatus:
    """Report Python without spawning a subprocess.

    ``sys.executable`` is the Manager bundle binary when frozen, so running it
    with ``--version`` would launch a second GUI instance. Report the in-process
    interpreter version directly instead.
    """
    version = sys.version.split()[0]
    if getattr(sys, "frozen", False):
        executable = "embedded"
        path = sys.executable
        message = f"Python {version} (embedded)"
    else:
        executable = sys.executable
        path = sys.executable
        message = f"Python {version}"
    trace_event("support.python_status", executable=executable, version=version, frozen=getattr(sys, "frozen", False))
    return ToolStatus("python", executable, path, version, True, message)


def renderer_status(path: Path | None) -> ToolStatus:
    if path is None:
        trace_event("support.renderer_status.default")
        return ToolStatus("renderer", "default", None, None, True, "using packaged/default renderer")
    return path_status("renderer", path, require_dir=True, writable=False)


def gh_auth_status(settings: ManagerSettings) -> ToolStatus:
    executable = settings.gh_executable
    trace_event("support.gh_auth.start", executable=executable)
    resolved = resolve_executable(executable)
    if resolved is None:
        trace_event("support.gh_auth.missing", executable=executable)
        return ToolStatus("gh_auth", executable, None, None, False, f"{executable} not found on Manager PATH")
    auth = run_command([resolved, "auth", "status"], timeout=8)
    output = (auth.stdout or auth.stderr).strip()
    ok = auth.returncode == 0
    message = output.splitlines()[0] if output else ("authenticated" if ok else f"exit {auth.returncode}")
    trace_event("support.gh_auth.done", ok=ok, returncode=auth.returncode, message=message)
    return ToolStatus("gh_auth", executable, resolved, None, ok, message)


def support_summary(settings: ManagerSettings, statuses: list[ToolStatus]) -> str:
    lines = [
        "bt-web-report Manager support summary",
        f"app_version: {__version__}",
        f"platform: {platform.platform()}",
        f"python: {sys.version.replace(chr(10), ' ')}",
        f"python_executable: {sys.executable}",
        f"cwd: {Path.cwd()}",
        f"trace_log: {trace_log_path()}",
        "",
        "settings:",
        f"  projects_root: {settings.projects_root}",
        f"  extra_project_paths: {[str(path) for path in settings.extra_project_paths]}",
        f"  hidden_project_paths: {[str(path) for path in settings.hidden_project_paths]}",
        f"  btwr_executable: {settings.btwr_executable}",
        f"  pnpm_executable: {settings.pnpm_executable}",
        f"  renderer_source: {settings.renderer_source}",
        f"  git_executable: {settings.git_executable}",
        f"  gh_executable: {settings.gh_executable}",
        f"  editor_command: {settings.editor_command}",
        f"  project_github_owner: {settings.project_github_owner}",
        "",
        "system_check:",
    ]
    for status in statuses:
        state = "OK" if status.ok else "WARN"
        lines.append(
            f"  {state} {status.name}: executable={status.executable} path={status.path} message={status.message}"
        )
    trace_event("support.summary.created", line_count=len(lines))
    return "\n".join(lines)
