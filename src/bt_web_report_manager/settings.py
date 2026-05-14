"""Manager settings stored outside project repositories."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from bt_web_report_manager.models import ManagerSettings, ToolStatus

APP_SUPPORT_ENV = "BTWR_MANAGER_APP_SUPPORT"


def app_support_dir() -> Path:
    override = os.environ.get(APP_SUPPORT_ENV)
    if override:
        return Path(override).expanduser()
    return Path("~/Library/Application Support/bt-web-report-manager").expanduser()


def settings_path(base_dir: Path | None = None) -> Path:
    return (base_dir or app_support_dir()) / "settings.yaml"


def load_settings(path: Path | None = None) -> ManagerSettings:
    target = path or settings_path()
    if not target.exists():
        return ManagerSettings(btwr_executable=_default_btwr_executable())
    raw = yaml.safe_load(target.read_text()) or {}
    return _settings_from_mapping(raw)


def save_settings(settings: ManagerSettings, path: Path | None = None) -> Path:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(_settings_to_mapping(settings), sort_keys=False))
    return target


def _settings_from_mapping(raw: dict[str, Any]) -> ManagerSettings:
    return ManagerSettings(
        projects_root=Path(raw.get("projects_root", ManagerSettings.projects_root)).expanduser(),
        extra_project_paths=tuple(Path(item).expanduser() for item in raw.get("extra_project_paths", [])),
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
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        probe = target_dir / ".write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        return ToolStatus("settings", str(target_dir), None, None, False, str(exc))
    return ToolStatus("settings", str(target_dir), str(target_dir), None, True, "settings folder writable")


def _optional_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value).expanduser()


def _default_btwr_executable() -> str:
    workspace_candidate = workspace_btwr_executable()
    if workspace_candidate is not None:
        return workspace_candidate
    return "btwr"


def workspace_btwr_executable() -> str | None:
    workspace_candidate = Path(__file__).resolve().parents[3] / ".venv" / "bin" / "btwr"
    if workspace_candidate.exists():
        return str(workspace_candidate)
    return None
