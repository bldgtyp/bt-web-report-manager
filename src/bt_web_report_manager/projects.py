"""Project discovery and status calculation."""

from __future__ import annotations

import getpass
import json
import os
import re
import socket
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML

from bt_web_report_manager.certification_pathways import CatalogPathway, validate_certification_pathways
from bt_web_report_manager.git_status import read_git_status
from bt_web_report_manager.locks import read_lock
from bt_web_report_manager.models import GitStatus, ManagerSettings, ProjectMetadata, ProjectStatus
from bt_web_report_manager.trace import trace_event, trace_exception

ACCESS_MODE_PUBLIC = "public"
ACCESS_MODE_CLOUDFLARE_OTP = "cloudflare_access_otp"
ACCESS_MODES = {ACCESS_MODE_PUBLIC, ACCESS_MODE_CLOUDFLARE_OTP}
ACCESS_MODE_LABELS = {
    ACCESS_MODE_PUBLIC: "Public, noindex",
    ACCESS_MODE_CLOUDFLARE_OTP: "Gated by Cloudflare OTP",
}
BTWR_REQUIRED_OTP_EMAILS = ("ed@bldgtyp.com", "john@bldgtyp.com")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def discover_projects(settings: ManagerSettings) -> list[ProjectStatus]:
    trace_event("projects.discover.start", settings=settings)
    paths: list[Path] = []
    paths.extend(_standard_project_paths(settings.projects_root))
    for extra in settings.extra_project_paths:
        trace_event("projects.discover.extra_path", path=extra)
        paths.extend(_candidate_paths(extra))

    seen: set[Path] = set()
    hidden_paths = _resolved_hidden_paths(settings.hidden_project_paths)
    statuses: list[ProjectStatus] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in hidden_paths:
            trace_event("projects.discover.skip_hidden", path=path, resolved=resolved)
            continue
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


def _resolved_hidden_paths(paths: tuple[Path, ...]) -> set[Path]:
    resolved: set[Path] = set()
    for path in paths:
        resolved.add(path.expanduser().resolve())
    return resolved


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
    if metadata.access_warning:
        warnings.append(metadata.access_warning)

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
    access_mode, access_allowed_emails, access_warning = _parse_project_access(publishing.get("access"))
    certification_pathways_show, certification_pathways_recommended = _parse_certification_pathways(
        raw.get("certification_pathways")
    )
    metadata = ProjectMetadata(
        slug=str(raw.get("slug") or project_path.name),
        project_title=str(raw.get("project_title") or raw.get("building_name") or project_path.name),
        client_name=_optional_str(raw.get("client_name")),
        building_name=_optional_str(raw.get("building_name")),
        phase=_optional_str(raw.get("phase")),
        phpp_path=phpp_path,
        data_dir=data_dir,
        production_url=_optional_str(publishing.get("production_url")),
        access_mode=access_mode,
        access_allowed_emails=access_allowed_emails,
        access_warning=access_warning,
        certification_pathways_show=certification_pathways_show,
        certification_pathways_recommended=certification_pathways_recommended,
    )
    trace_event("projects.metadata.done", path=project_yaml, metadata=metadata)
    return metadata


def _parse_certification_pathways(value: Any) -> tuple[tuple[str, ...] | None, str | None]:
    # A malformed block reads as the default rather than failing the whole metadata
    # read; the renderer build reports the schema error.
    if not isinstance(value, dict):
        return None, None
    show = value.get("show")
    recommended = value.get("recommended")
    if not isinstance(show, list) or any(not isinstance(item, str) for item in show):
        return None, None
    return tuple(show), recommended if isinstance(recommended, str) else None


def _parse_project_access(access: Any) -> tuple[str, tuple[str, ...], str | None]:
    if access is None:
        return ACCESS_MODE_PUBLIC, (), None
    if not isinstance(access, dict):
        return ACCESS_MODE_PUBLIC, (), "publishing.access must be a mapping."

    raw_mode = access.get("mode", ACCESS_MODE_PUBLIC)
    mode = str(raw_mode)
    warning: str | None = None
    if mode not in ACCESS_MODES:
        warning = f"publishing.access.mode is unknown: {mode}"
        mode = ACCESS_MODE_PUBLIC

    raw_emails = access.get("allowed_emails", [])
    if not isinstance(raw_emails, list):
        return mode, (), "publishing.access.allowed_emails must be a list."

    try:
        emails = normalize_access_emails(raw_emails)
    except ValueError as exc:
        return mode, (), str(exc)
    if mode == ACCESS_MODE_CLOUDFLARE_OTP:
        missing = [email for email in BTWR_REQUIRED_OTP_EMAILS if email not in emails]
        if missing:
            warning = "publishing.access.allowed_emails is missing required BLDGTYP email(s): " + ", ".join(missing)
    return mode, tuple(emails), warning


def set_project_phpp_path(project_path: Path, phpp_path: Path | None) -> Path:
    """Update ``source_files.phpp_path`` in a content-only project's project.yaml."""
    project_yaml = project_path / "project.yaml"
    trace_event(
        "projects.phpp_path.set.start", project_path=project_path, project_yaml=project_yaml, phpp_path=phpp_path
    )
    if not project_yaml.exists():
        msg = f"project.yaml does not exist: {project_yaml}"
        raise ValueError(msg)
    if phpp_path is not None:
        phpp_path = phpp_path.expanduser().resolve()
        if not phpp_path.exists():
            msg = f"PHPP workbook does not exist: {phpp_path}"
            raise ValueError(msg)
        if not phpp_path.is_file():
            msg = f"PHPP path is not a file: {phpp_path}"
            raise ValueError(msg)
        if phpp_path.suffix.lower() not in {".xlsx", ".xlsm"}:
            msg = "PHPP workbook must be an .xlsx or .xlsm file."
            raise ValueError(msg)

    raw = _read_project_yaml_mapping(project_yaml)
    source_files = _ensure_mapping_section(raw, "source_files")
    if phpp_path is None:
        source_files["phpp_path"] = ""
    else:
        source_files["phpp_path"] = os.path.relpath(phpp_path, project_path)
    project_yaml.write_text(yaml.safe_dump(raw, sort_keys=False))
    trace_event(
        "projects.phpp_path.set.done",
        project_path=project_path,
        project_yaml=project_yaml,
        phpp_path=phpp_path,
        stored=source_files["phpp_path"],
    )
    return project_yaml


def set_project_access(project_path: Path, mode: str, allowed_emails: list[str] | tuple[str, ...]) -> Path:
    """Update ``publishing.access`` in a content-only project's project.yaml."""
    project_yaml = project_path / "project.yaml"
    trace_event(
        "projects.access.set.start",
        project_path=project_path,
        project_yaml=project_yaml,
        mode=mode,
        allowed_emails=allowed_emails,
    )
    if not project_yaml.exists():
        msg = f"project.yaml does not exist: {project_yaml}"
        raise ValueError(msg)
    if mode not in ACCESS_MODES:
        msg = f"Report access mode must be one of: {', '.join(sorted(ACCESS_MODES))}."
        raise ValueError(msg)

    raw, yaml_rt = _read_project_yaml_round_trip(project_yaml)
    publishing = _ensure_mapping_section(raw, "publishing")

    emails = normalize_access_emails(allowed_emails)
    if mode == ACCESS_MODE_PUBLIC:
        emails = []
    else:
        emails = normalize_access_emails([*emails, *BTWR_REQUIRED_OTP_EMAILS])
        if not emails:
            msg = "Cloudflare OTP access requires at least one allowed email."
            raise ValueError(msg)

    publishing["access"] = {"mode": mode, "allowed_emails": emails}
    _write_project_yaml_round_trip(project_yaml, yaml_rt, raw)
    trace_event(
        "projects.access.set.done",
        project_path=project_path,
        project_yaml=project_yaml,
        mode=mode,
        allowed_emails=emails,
    )
    return project_yaml


def set_certification_pathways(
    project_path: Path,
    show: list[str] | tuple[str, ...],
    recommended: str | None,
    catalog: list[CatalogPathway] | tuple[CatalogPathway, ...] | None = None,
) -> Path:
    """Set an explicit ordered certification-pathway selection in project.yaml."""
    project_yaml = project_path / "project.yaml"
    trace_event(
        "projects.certification_pathways.set.start",
        project_path=project_path,
        project_yaml=project_yaml,
        show=show,
        recommended=recommended,
    )
    if not project_yaml.exists():
        raise ValueError(f"project.yaml does not exist: {project_yaml}")
    normalized_show, normalized_recommended = validate_certification_pathways(show, recommended, catalog)
    raw, yaml_rt = _read_project_yaml_round_trip(project_yaml)
    selection = _ensure_mapping_section(raw, "certification_pathways")
    selection["show"] = list(normalized_show)
    if normalized_recommended is not None:
        selection["recommended"] = normalized_recommended
    else:
        selection.pop("recommended", None)
    _write_project_yaml_round_trip(project_yaml, yaml_rt, raw)
    trace_event(
        "projects.certification_pathways.set.done",
        project_path=project_path,
        project_yaml=project_yaml,
        show=normalized_show,
        recommended=normalized_recommended,
    )
    return project_yaml


def clear_certification_pathways(project_path: Path) -> Path:
    """Remove the explicit selection so the renderer uses its default pathways."""
    project_yaml = project_path / "project.yaml"
    trace_event("projects.certification_pathways.clear.start", project_path=project_path, project_yaml=project_yaml)
    if not project_yaml.exists():
        raise ValueError(f"project.yaml does not exist: {project_yaml}")
    raw, yaml_rt = _read_project_yaml_round_trip(project_yaml)
    raw.pop("certification_pathways", None)
    _write_project_yaml_round_trip(project_yaml, yaml_rt, raw)
    trace_event("projects.certification_pathways.clear.done", project_path=project_path, project_yaml=project_yaml)
    return project_yaml


def normalize_access_emails(values: list[str] | tuple[str, ...]) -> list[str]:
    emails: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str):
            msg = f"Allowed email #{index + 1} must be a string."
            raise ValueError(msg)
        email = value.strip().lower()
        if not email:
            continue
        if not EMAIL_RE.fullmatch(email):
            msg = f"Allowed email is not valid: {value}"
            raise ValueError(msg)
        if email not in seen:
            emails.append(email)
            seen.add(email)
    return emails


def access_mode_label(mode: str) -> str:
    return ACCESS_MODE_LABELS.get(mode, ACCESS_MODE_LABELS[ACCESS_MODE_PUBLIC])


def _read_project_yaml_mapping(project_yaml: Path) -> dict[str, Any]:
    raw = yaml.safe_load(project_yaml.read_text()) or {}
    if not isinstance(raw, dict):
        msg = f"project.yaml must contain a mapping: {project_yaml}"
        raise ValueError(msg)
    return raw


def _ensure_mapping_section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    section = raw.get(key)
    if not isinstance(section, dict):
        section = {}
        raw[key] = section
    return section


def _read_project_yaml_round_trip(project_yaml: Path) -> tuple[dict[str, Any], YAML]:
    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    raw = yaml_rt.load(project_yaml.read_text()) or {}
    if not isinstance(raw, dict):
        msg = f"project.yaml must contain a mapping: {project_yaml}"
        raise ValueError(msg)
    return raw, yaml_rt


def _write_project_yaml_round_trip(project_yaml: Path, yaml_rt: YAML, raw: dict[str, Any]) -> None:
    stream = StringIO()
    yaml_rt.dump(raw, stream)
    project_yaml.write_text(stream.getvalue())


def validate_project_web_root(path: Path) -> Path:
    """Resolve and validate a replacement project web-root folder."""
    root = path.expanduser().resolve()
    trace_event("projects.web_root.validate.start", path=path, resolved=root)
    if not root.exists():
        msg = f"Web root does not exist: {root}"
        raise ValueError(msg)
    if not root.is_dir():
        msg = f"Web root is not a folder: {root}"
        raise ValueError(msg)
    if not (root / "project.yaml").exists():
        msg = f"Web root must contain project.yaml: {root}"
        raise ValueError(msg)
    # Parse once so a bad replacement root fails before Manager settings are changed.
    read_project_metadata(root)
    trace_event("projects.web_root.validate.done", resolved=root)
    return root


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
