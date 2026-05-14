"""Dropbox-synced soft-lock helpers."""

from __future__ import annotations

import getpass
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from bt_web_report_manager import __version__
from bt_web_report_manager.models import LockInfo
from bt_web_report_manager.trace import trace_event, trace_exception


def current_user() -> str:
    return getpass.getuser()


def current_host() -> str:
    return socket.gethostname()


def lock_path(project_path: Path) -> Path:
    return project_path / ".bldgtyp" / "lock.yaml"


def read_lock(project_path: Path) -> LockInfo | None:
    path = lock_path(project_path)
    if not path.exists():
        trace_event("locks.read.missing", project_path=project_path, path=path)
        return None
    try:
        raw = yaml.safe_load(path.read_text()) or {}
        lock = _lock_from_mapping(path, raw)
        trace_event("locks.read.done", project_path=project_path, path=path, lock=lock)
        return lock
    except Exception as exc:
        trace_exception("locks.read.failed", exc, project_path=project_path, path=path)
        return LockInfo(path=path, malformed=True)


def write_lock(project_path: Path, project_slug: str, ttl_hours: int, now: datetime | None = None) -> LockInfo:
    trace_event("locks.write.start", project_path=project_path, project_slug=project_slug, ttl_hours=ttl_hours)
    current = now or datetime.now(timezone.utc).astimezone()
    info = LockInfo(
        path=lock_path(project_path),
        user=current_user(),
        host=current_host(),
        project_slug=project_slug,
        opened_at=current,
        updated_at=current,
        expires_at=current + timedelta(hours=ttl_hours),
    )
    info.path.parent.mkdir(parents=True, exist_ok=True)
    info.path.write_text(yaml.safe_dump(_lock_to_mapping(info), sort_keys=False))
    trace_event("locks.write.done", project_path=project_path, path=info.path, lock=info)
    return info


def refresh_lock(project_path: Path, ttl_hours: int, now: datetime | None = None) -> LockInfo | None:
    trace_event("locks.refresh.start", project_path=project_path, ttl_hours=ttl_hours)
    existing = read_lock(project_path)
    if existing is None or existing.malformed:
        trace_event("locks.refresh.skipped", project_path=project_path, existing=existing)
        return existing
    current = now or datetime.now(timezone.utc).astimezone()
    refreshed = LockInfo(
        path=existing.path,
        user=existing.user,
        host=existing.host,
        project_slug=existing.project_slug,
        opened_at=existing.opened_at,
        updated_at=current,
        expires_at=current + timedelta(hours=ttl_hours),
    )
    refreshed.path.write_text(yaml.safe_dump(_lock_to_mapping(refreshed), sort_keys=False))
    trace_event("locks.refresh.done", project_path=project_path, lock=refreshed)
    return refreshed


def release_lock(project_path: Path) -> None:
    path = lock_path(project_path)
    if path.exists():
        path.unlink()
        trace_event("locks.release.done", project_path=project_path, path=path)
    else:
        trace_event("locks.release.missing", project_path=project_path, path=path)


def is_current_user_lock(lock: LockInfo) -> bool:
    return lock.user == current_user() and lock.host == current_host()


def lock_requires_confirmation(lock: LockInfo | None, now: datetime | None = None) -> bool:
    if lock is None:
        trace_event("locks.requires_confirmation", lock=None, required=False)
        return False
    if lock.malformed:
        trace_event("locks.requires_confirmation", lock=lock, required=True, reason="malformed")
        return True
    current = now or datetime.now(timezone.utc).astimezone()
    if lock.is_expired(current):
        trace_event("locks.requires_confirmation", lock=lock, required=False, reason="expired")
        return False
    required = not is_current_user_lock(lock)
    trace_event(
        "locks.requires_confirmation", lock=lock, required=required, reason="other_user" if required else "current_user"
    )
    return required


def lock_warning_message(lock: LockInfo) -> str:
    if lock.malformed:
        return f"The lock file is malformed:\n{lock.path}\n\nContinue and replace it?"
    owner = lock.user or "unknown user"
    host = lock.host or "unknown host"
    expires = lock.expires_at.isoformat() if lock.expires_at is not None else "unknown"
    return f"This project is locked by {owner} on {host} until {expires}.\n\nContinue and replace the lock?"


def _lock_from_mapping(path: Path, raw: dict[str, Any]) -> LockInfo:
    return LockInfo(
        path=path,
        user=_optional_str(raw.get("user")),
        host=_optional_str(raw.get("host")),
        project_slug=_optional_str(raw.get("project_slug")),
        opened_at=_parse_datetime(raw.get("opened_at")),
        updated_at=_parse_datetime(raw.get("updated_at")),
        expires_at=_parse_datetime(raw.get("expires_at")),
    )


def _lock_to_mapping(info: LockInfo) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "user": info.user,
        "host": info.host,
        "app_version": __version__,
        "project_slug": info.project_slug,
        "opened_at": _format_datetime(info.opened_at),
        "updated_at": _format_datetime(info.updated_at),
        "expires_at": _format_datetime(info.expires_at),
    }


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
