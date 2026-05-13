"""Project discovery and status calculation."""

from __future__ import annotations

import json
import getpass
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from bt_web_report_manager.git_status import read_git_status
from bt_web_report_manager.locks import read_lock
from bt_web_report_manager.models import GitStatus, ManagerSettings, ProjectMetadata, ProjectStatus


def discover_projects(settings: ManagerSettings) -> list[ProjectStatus]:
    paths: list[Path] = []
    paths.extend(_standard_project_paths(settings.projects_root))
    for extra in settings.extra_project_paths:
        paths.extend(_candidate_paths(extra))

    seen: set[Path] = set()
    statuses: list[ProjectStatus] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        statuses.append(read_project_status(resolved, settings))
    return sorted(statuses, key=lambda item: item.metadata.slug)


def read_project_status(project_path: Path, settings: ManagerSettings) -> ProjectStatus:
    warnings: list[str] = []
    try:
        metadata = read_project_metadata(project_path)
    except Exception as exc:
        metadata = ProjectMetadata(
            slug=project_path.name,
            project_title=project_path.name,
            client_name=None,
            building_name=None,
            phase=None,
            phpp_path=None,
            data_dir=project_path / "data",
            production_url=None,
        )
        warnings.append(f"project.yaml could not be parsed: {exc}")

    manifest_path = metadata.data_dir / "manifest.json"
    manifest_generated_at = _read_manifest_generated_at(manifest_path, warnings) if manifest_path.exists() else None
    phpp_modified_at = _mtime(metadata.phpp_path) if metadata.phpp_path and metadata.phpp_path.exists() else None
    if metadata.phpp_path and not metadata.phpp_path.exists():
        warnings.append(f"PHPP workbook missing: {metadata.phpp_path}")

    git = read_git_status(project_path, settings.git_executable)
    lock = read_lock(project_path)
    status = ProjectStatus(
        project_path=project_path,
        metadata=metadata,
        git=git,
        lock=lock,
        manifest_path=manifest_path if manifest_path.exists() else None,
        manifest_generated_at=manifest_generated_at,
        phpp_modified_at=phpp_modified_at,
        warnings=tuple(warnings),
    )
    return _with_badges(status, now=datetime.now(timezone.utc).astimezone())


def read_project_metadata(project_path: Path) -> ProjectMetadata:
    raw = yaml.safe_load((project_path / "project.yaml").read_text()) or {}
    source_files = raw.get("source_files") or {}
    publishing = raw.get("publishing") or {}
    phpp_raw = source_files.get("phpp_path")
    data_raw = source_files.get("data_dir", "data")
    phpp_path = (project_path / phpp_raw).resolve() if phpp_raw else None
    data_dir = (project_path / data_raw).resolve()
    return ProjectMetadata(
        slug=str(raw.get("slug") or project_path.name),
        project_title=str(raw.get("project_title") or raw.get("building_name") or project_path.name),
        client_name=_optional_str(raw.get("client_name")),
        building_name=_optional_str(raw.get("building_name")),
        phase=_optional_str(raw.get("phase")),
        phpp_path=phpp_path,
        data_dir=data_dir,
        production_url=_optional_str(publishing.get("production_url")),
    )


def _standard_project_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    paths: list[Path] = []
    for project_dir in root.iterdir():
        if not project_dir.is_dir():
            continue
        for child_name in ("04_Web", "04_Web_next"):
            child = project_dir / child_name
            if (child / "project.yaml").exists():
                paths.append(child)
    return paths


def _candidate_paths(path: Path) -> list[Path]:
    if (path / "project.yaml").exists():
        return [path]
    return _standard_project_paths(path)


def _read_manifest_generated_at(path: Path, warnings: list[str]) -> datetime | None:
    try:
        raw: dict[str, Any] = json.loads(path.read_text())
        value = raw.get("generated_at")
        if not isinstance(value, str):
            warnings.append("manifest.json has no generated_at timestamp")
            return _mtime(path)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception as exc:
        warnings.append(f"manifest.json could not be parsed: {exc}")
        return _mtime(path)


def _with_badges(status: ProjectStatus, now: datetime | None = None) -> ProjectStatus:
    current_time = now or datetime.now(timezone.utc).astimezone()
    badges: list[str] = []
    if status.needs_scrape:
        badges.append("Needs scrape" if status.manifest_path else "No data")
    else:
        badges.append("Data current")
    if not status.git.is_repo:
        badges.append("No git")
    elif status.git.dirty_count:
        badges.append(f"Dirty ({status.git.dirty_count})")
    else:
        badges.append("Git clean")
    if status.lock is not None:
        badges.append(_lock_badge(status.lock, current_time))
    if status.warnings:
        badges.append("Warnings")
    return ProjectStatus(
        project_path=status.project_path,
        metadata=status.metadata,
        git=status.git,
        lock=status.lock,
        manifest_path=status.manifest_path,
        manifest_generated_at=status.manifest_generated_at,
        phpp_modified_at=status.phpp_modified_at,
        warnings=status.warnings,
        badges=tuple(badges),
    )


def _mtime(path: Path | None) -> datetime | None:
    if path is None or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def empty_git_status() -> GitStatus:
    return GitStatus(False)


def _lock_badge(lock: object, now: datetime) -> str:
    from bt_web_report_manager.models import LockInfo

    if not isinstance(lock, LockInfo):
        return "Lock unknown"
    if lock.malformed:
        return "Lock malformed"
    if lock.is_expired(now):
        return "Stale lock"
    if lock.user == getpass.getuser() and lock.host == socket.gethostname():
        return "Locked by you"
    owner = lock.user or "unknown"
    return f"Locked by {owner}"
