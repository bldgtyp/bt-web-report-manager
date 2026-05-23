"""Reader for ``<project>/.bldgtyp/platform.yaml``.

Phase 4 surface for the seed provenance stamped by ``btwr new`` (and
updated by ``btwr re-seed``). The Manager UI uses this to badge each
project row with its vendored renderer SHA + age, so a quick glance
reveals which projects are running stale renderers.

Schema (all fields optional — missing keys collapse to ``None``):

    renderer_seed_ref: <40-char SHA or short SHA>
    schemas_pin:       <npm spec, e.g. "^0.3.0">
    cli_version:       <semver string>
    seeded_at:         <ISO 8601 UTC, e.g. "2026-05-23T02:41:15Z">
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from bt_web_report_manager.models import PlatformInfo
from bt_web_report_manager.trace import trace_exception

PLATFORM_FILE = Path(".bldgtyp") / "platform.yaml"


def read_platform_info(project_path: Path) -> PlatformInfo | None:
    """Return parsed platform.yaml or ``None`` if absent / unreadable.

    Returns ``None`` (not an empty PlatformInfo) for pre-vendored projects so
    the UI can distinguish "no provenance recorded" from "provenance recorded
    but partially missing."
    """

    file_path = project_path / PLATFORM_FILE
    if not file_path.exists():
        return None
    try:
        raw = yaml.safe_load(file_path.read_text())
    except yaml.YAMLError as exc:
        trace_exception("platform_yaml.parse_error", exc, project=str(project_path))
        return PlatformInfo()
    if not isinstance(raw, dict):
        return PlatformInfo()

    return PlatformInfo(
        renderer_seed_ref=_optional_str(raw, "renderer_seed_ref"),
        schemas_pin=_optional_str(raw, "schemas_pin"),
        cli_version=_optional_str(raw, "cli_version"),
        seeded_at=_parse_iso(raw.get("seeded_at")),
    )


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_iso(value: Any) -> datetime | None:
    """Parse the platform.yaml's ISO 8601 timestamp; tolerate the Z suffix."""

    if not isinstance(value, str) or not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def short_ref(ref: str | None, length: int = 7) -> str:
    """Return a short ref suitable for UI display."""

    if not ref:
        return "unknown"
    return ref[:length]
