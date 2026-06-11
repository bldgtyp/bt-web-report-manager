"""Manager settings stored outside project repositories."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from bt_web_report_manager.models import ManagerSettings, ToolStatus
from bt_web_report_manager.trace import trace_event

APP_SUPPORT_ENV = "BTWR_MANAGER_APP_SUPPORT"
WORKSPACE_ROOT_ENV = "BTWR_WORKSPACE_ROOT"
WORKSPACE_MARKER_TOKEN = "bt-web-report-cli"
WORKSPACE_SEARCH_HINTS: tuple[Path, ...] = (
    Path("~/Dropbox/bldgtyp-00/00_PH_Tools/bldgtyp/bt-web-report").expanduser(),
    Path("~/Dropbox/bldgtyp-00/00_PH_Tools/bt-web-report").expanduser(),
    Path("~/00_PH_Tools/bldgtyp/bt-web-report").expanduser(),
    Path("~/bt-web-report").expanduser(),
)


def app_support_dir() -> Path:
    override = os.environ.get(APP_SUPPORT_ENV)
    if override:
        path = Path(override).expanduser()
        trace_event("settings.app_support_dir", source="env", path=path)
        return path
    path = Path("~/Library/Application Support/bt-web-report-manager").expanduser()
    trace_event("settings.app_support_dir", source="default", path=path)
    return path


def settings_path(base_dir: Path | None = None) -> Path:
    return (base_dir or app_support_dir()) / "settings.yaml"


def project_runtime_dirs(slug: str, base_dir: Path | None = None) -> tuple[Path, ...]:
    """Return manager-owned runtime folders that are disposable for one project."""
    root = base_dir or app_support_dir()
    return (root / "builds" / slug, root / "previews" / slug)


def cleanup_project_runtime(slug: str, base_dir: Path | None = None) -> tuple[Path, ...]:
    """Remove manager-owned build/preview workspaces for ``slug``."""
    removed: list[Path] = []
    for path in project_runtime_dirs(slug, base_dir):
        if not path.exists() and not path.is_symlink():
            trace_event("settings.cleanup_project_runtime.missing", slug=slug, path=path)
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path)
        trace_event("settings.cleanup_project_runtime.removed", slug=slug, path=path)
    trace_event("settings.cleanup_project_runtime.done", slug=slug, removed=removed)
    return tuple(removed)


def load_settings(path: Path | None = None) -> ManagerSettings:
    target = path or settings_path()
    trace_event("settings.load.start", path=target, exists=target.exists())
    if not target.exists():
        settings = ManagerSettings(btwr_executable=_default_btwr_executable())
        trace_event("settings.load.missing", path=target, settings=_settings_to_mapping(settings))
        return settings
    raw = yaml.safe_load(target.read_text()) or {}
    settings = _settings_from_mapping(raw)
    trace_event("settings.load.done", path=target, raw=raw, settings=_settings_to_mapping(settings))
    return settings


def save_settings(settings: ManagerSettings, path: Path | None = None) -> Path:
    target = path or settings_path()
    trace_event("settings.save.start", path=target, settings=_settings_to_mapping(settings))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(_settings_to_mapping(settings), sort_keys=False))
    trace_event("settings.save.done", path=target)
    return target


def unhide_project_path(settings: ManagerSettings, project_path: Path) -> ManagerSettings:
    """Return settings with ``project_path`` removed from hidden-project filters."""
    target = _resolved_path(project_path)
    visible_paths = tuple(path for path in settings.hidden_project_paths if _resolved_path(path) != target)
    if visible_paths == settings.hidden_project_paths:
        trace_event("settings.unhide_project_path.noop", project_path=project_path, target=target)
        return settings
    updated = ManagerSettings(
        projects_root=settings.projects_root,
        extra_project_paths=settings.extra_project_paths,
        hidden_project_paths=visible_paths,
        btwr_executable=settings.btwr_executable,
        pnpm_executable=settings.pnpm_executable,
        renderer_source=settings.renderer_source,
        git_executable=settings.git_executable,
        gh_executable=settings.gh_executable,
        editor_command=settings.editor_command,
        github_owner=settings.github_owner,
        github_repo=settings.github_repo,
        project_github_owner=settings.project_github_owner,
        lock_ttl_hours=settings.lock_ttl_hours,
    )
    trace_event(
        "settings.unhide_project_path.removed",
        project_path=project_path,
        target=target,
        hidden_before=settings.hidden_project_paths,
        hidden_after=visible_paths,
    )
    return updated


def _settings_from_mapping(raw: dict[str, Any]) -> ManagerSettings:
    return ManagerSettings(
        projects_root=Path(raw.get("projects_root", ManagerSettings.projects_root)).expanduser(),
        extra_project_paths=tuple(Path(item).expanduser() for item in raw.get("extra_project_paths", [])),
        hidden_project_paths=tuple(Path(item).expanduser() for item in raw.get("hidden_project_paths", [])),
        btwr_executable=str(raw.get("btwr_executable") or _default_btwr_executable()),
        pnpm_executable=str(raw.get("pnpm_executable", "pnpm")),
        renderer_source=_optional_path(raw.get("renderer_source")),
        git_executable=str(raw.get("git_executable", "git")),
        gh_executable=str(raw.get("gh_executable", "gh")),
        editor_command=str(raw.get("editor_command", "code")),
        github_owner=str(raw.get("github_owner", "bldgtyp")),
        github_repo=str(raw.get("github_repo", "bt-web-report-manager")),
        project_github_owner=str(raw.get("project_github_owner", "bldgtyp-projects")),
        lock_ttl_hours=int(raw.get("lock_ttl_hours", 4)),
    )


def _settings_to_mapping(settings: ManagerSettings) -> dict[str, Any]:
    return {
        "projects_root": str(settings.projects_root),
        "extra_project_paths": [str(path) for path in settings.extra_project_paths],
        "hidden_project_paths": [str(path) for path in settings.hidden_project_paths],
        "btwr_executable": settings.btwr_executable,
        "pnpm_executable": settings.pnpm_executable,
        "renderer_source": str(settings.renderer_source) if settings.renderer_source is not None else None,
        "git_executable": settings.git_executable,
        "gh_executable": settings.gh_executable,
        "editor_command": settings.editor_command,
        "github_owner": settings.github_owner,
        "github_repo": settings.github_repo,
        "project_github_owner": settings.project_github_owner,
        "lock_ttl_hours": settings.lock_ttl_hours,
    }


def settings_write_status(base_dir: Path | None = None) -> ToolStatus:
    target_dir = base_dir or app_support_dir()
    trace_event("settings.write_status.start", path=target_dir)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        probe = target_dir / ".write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        trace_event("settings.write_status.failed", path=target_dir, error=str(exc))
        return ToolStatus("settings", str(target_dir), None, None, False, str(exc))
    trace_event("settings.write_status.ok", path=target_dir)
    return ToolStatus("settings", str(target_dir), str(target_dir), None, True, "settings folder writable")


def _optional_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value).expanduser()


def _resolved_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _default_btwr_executable() -> str:
    workspace_candidate = workspace_btwr_executable()
    if workspace_candidate is not None:
        trace_event("settings.default_btwr.workspace", path=workspace_candidate)
        return workspace_candidate
    trace_event("settings.default_btwr.path_name", executable="btwr")
    return "btwr"


def workspace_btwr_executable() -> str | None:
    for workspace_root in workspace_root_candidates():
        workspace_candidate = workspace_root / ".venv" / "bin" / "btwr"
        trace_event(
            "settings.workspace_btwr.candidate",
            workspace_root=workspace_root,
            path=workspace_candidate,
            exists=workspace_candidate.exists(),
        )
        if workspace_candidate.exists():
            trace_event("settings.workspace_btwr.found", path=workspace_candidate)
            return str(workspace_candidate)
    uv_tool_candidate = Path("~/.local/bin/btwr").expanduser()
    trace_event(
        "settings.workspace_btwr.uv_tool_candidate",
        path=uv_tool_candidate,
        exists=uv_tool_candidate.exists(),
    )
    if uv_tool_candidate.exists():
        trace_event("settings.workspace_btwr.uv_tool_found", path=uv_tool_candidate)
        return str(uv_tool_candidate)
    trace_event("settings.workspace_btwr.not_found")
    return None


def workspace_root_candidates() -> tuple[Path, ...]:
    """Locate the bt-web-report workspace root via multiple strategies.

    Strategies, in priority order:
      1. ``BTWR_WORKSPACE_ROOT`` env var (escape hatch).
      2. Walk-up from this file (works in source checkouts; PyInstaller bundles fail here).
      3. Walk-up from CWD.
      4. Walk-up from common Dropbox/PH_Tools hint paths.
      5. Direct hint paths as a last-resort fallback.

    A "workspace root" is identified by a ``pyproject.toml`` containing the
    marker token ``bt-web-report-cli`` — survives moves, renames, and
    Dropbox-path differences across machines.
    """
    found: list[Path] = []

    env_root = os.environ.get(WORKSPACE_ROOT_ENV)
    if env_root:
        candidate = Path(env_root).expanduser()
        if _is_workspace_root(candidate):
            found.append(candidate)
            trace_event("settings.workspace_root.env", path=candidate)

    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for parent in (start, *start.parents):
            if _is_workspace_root(parent):
                found.append(parent)
                trace_event("settings.workspace_root.walkup", start=start, path=parent)
                break

    for hint in WORKSPACE_SEARCH_HINTS:
        if _is_workspace_root(hint):
            found.append(hint)
            trace_event("settings.workspace_root.hint", path=hint)
        elif hint.exists():
            for parent in (hint, *hint.parents):
                if _is_workspace_root(parent):
                    found.append(parent)
                    trace_event("settings.workspace_root.hint_walkup", start=hint, path=parent)
                    break

    found.extend(WORKSPACE_SEARCH_HINTS)

    return tuple(dict.fromkeys(found))


def _is_workspace_root(path: Path) -> bool:
    pyproject = path / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return WORKSPACE_MARKER_TOKEN in text
