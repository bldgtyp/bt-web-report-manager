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
from bt_web_report_manager.trace import trace_event, trace_exception


def discover_projects(settings: ManagerSettings) -> list[ProjectStatus]:
    trace_event("projects.discover.start", settings=settings)
    paths: list[Path] = []
    paths.extend(_standard_project_paths(settings.projects_root))
    for extra in settings.extra_project_paths:
        trace_event("projects.discover.extra_path", path=extra)
        paths.extend(_candidate_paths(extra))

    seen: set[Path] = set()
    statuses: list[ProjectStatus] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            trace_event("projects.discover.skip_duplicate", path=path, resolved=resolved)
            continue
        seen.add(resolved)
        trace_event("projects.discover.read_status", path=path, resolved=resolved)
        statuses.append(read_project_status(resolved, settings))
    sorted_statuses = sorted(statuses, key=lambda item: item.metadata.slug)
    trace_event(
        "projects.discover.done",
        count=len(sorted_statuses),
        projects=[{"slug": status.metadata.slug, "path": status.project_path} for status in sorted_statuses],
    )
    return sorted_statuses


def read_project_status(project_path: Path, settings: ManagerSettings) -> ProjectStatus:
    trace_event("projects.status.start", path=project_path)
    warnings: list[str] = []
    try:
        metadata = read_project_metadata(project_path)
    except Exception as exc:
        trace_exception("projects.status.metadata_failed", exc, path=project_path)
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
    status_with_badges = _with_badges(status, now=datetime.now(timezone.utc).astimezone())
    trace_event(
        "projects.status.done",
        path=project_path,
        slug=status_with_badges.metadata.slug,
        warnings=status_with_badges.warnings,
        badges=status_with_badges.badges,
        manifest_path=status_with_badges.manifest_path,
        phpp_path=status_with_badges.metadata.phpp_path,
    )
    return status_with_badges


def read_project_metadata(project_path: Path) -> ProjectMetadata:
    project_yaml = project_path / "project.yaml"
    trace_event("projects.metadata.read", path=project_yaml, exists=project_yaml.exists())
    raw = yaml.safe_load((project_path / "project.yaml").read_text()) or {}
    source_files = raw.get("source_files") or {}
    publishing = raw.get("publishing") or {}
    phpp_raw = source_files.get("phpp_path")
    data_raw = source_files.get("data_dir", "data")
    phpp_path = (project_path / phpp_raw).resolve() if phpp_raw else None
    data_dir = (project_path / data_raw).resolve()
    metadata = ProjectMetadata(
        slug=str(raw.get("slug") or project_path.name),
        project_title=str(raw.get("project_title") or raw.get("building_name") or project_path.name),
        client_name=_optional_str(raw.get("client_name")),
        building_name=_optional_str(raw.get("building_name")),
        phase=_optional_str(raw.get("phase")),
        phpp_path=phpp_path,
        data_dir=data_dir,
        production_url=_optional_str(publishing.get("production_url")),
    )
    trace_event("projects.metadata.done", path=project_yaml, metadata=metadata)
    return metadata


def _standard_project_paths(root: Path) -> list[Path]:
    if not root.exists():
        trace_event("projects.standard_paths.root_missing", root=root)
        return []
    trace_event("projects.standard_paths.scan_root", root=root)
    paths: list[Path] = []
    for project_dir in root.iterdir():
        if not project_dir.is_dir():
            trace_event("projects.standard_paths.skip_non_dir", path=project_dir)
            continue
        for child_name in ("04_Web", "04_Web_next"):
            child = project_dir / child_name
            trace_event(
                "projects.standard_paths.check_child",
                child=child,
                project_yaml=child / "project.yaml",
                exists=(child / "project.yaml").exists(),
            )
            if (child / "project.yaml").exists():
                paths.append(child)
    trace_event("projects.standard_paths.done", root=root, paths=paths)
    return paths


def _candidate_paths(path: Path) -> list[Path]:
    if (path / "project.yaml").exists():
        trace_event("projects.candidate.direct_project", path=path)
        return [path]
    trace_event("projects.candidate.scan_as_root", path=path)
    return _standard_project_paths(path)


def _read_manifest_generated_at(path: Path, warnings: list[str]) -> datetime | None:
    trace_event("projects.manifest.read", path=path)
    try:
        raw: dict[str, Any] = json.loads(path.read_text())
        value = raw.get("generated_at")
        if not isinstance(value, str):
            if raw.get("status") == "pending":
                trace_event("projects.manifest.pending_without_generated_at", path=path)
                return None
            warnings.append("manifest.json has no generated_at timestamp")
            trace_event("projects.manifest.missing_generated_at", path=path)
            return _mtime(path)
        generated_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        trace_event("projects.manifest.done", path=path, generated_at=generated_at)
        return generated_at
    except Exception as exc:
        trace_exception("projects.manifest.failed", exc, path=path)
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
