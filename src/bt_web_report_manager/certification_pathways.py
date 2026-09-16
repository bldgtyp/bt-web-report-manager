"""Certification-pathway catalog discovery and selection validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Sequence

from bt_web_report_manager.settings import app_support_dir, workspace_root_candidates
from bt_web_report_manager.trace import trace_event

CERTIFICATION_CATALOG_ENV = "BTWR_MANAGER_CERTIFICATION_PATHWAYS_JSON"
CERTIFICATION_CATALOG_RELATIVE_PATH = Path("src/data/certification-pathways.json")
CERTIFICATION_PATHWAY_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Mirrors the renderer template's default for projects without a certification_pathways block.
DEFAULT_CERTIFICATION_PATHWAY_IDS = (
    "phi-classic",
    "phi-leb",
    "phius-core-2024",
    "phius-zero-2024",
)


@dataclass(frozen=True)
class CatalogPathway:
    id: str
    title: str


class CertificationCatalogError(ValueError):
    """Raised when the renderer certification catalog cannot be loaded."""


def load_certification_catalog(renderer_source: Path | None = None) -> list[CatalogPathway]:
    """Load the first available renderer-owned certification catalog."""
    candidates = _certification_catalog_candidates(renderer_source)
    for candidate in candidates:
        if not candidate.exists():
            trace_event("certification.catalog.candidate_missing", path=candidate)
            continue
        trace_event("certification.catalog.read", path=candidate)
        try:
            raw = json.loads(candidate.read_text())
        except (OSError, UnicodeError) as exc:
            msg = f"Certification pathways catalog could not be read: {candidate}: {exc}"
            raise CertificationCatalogError(msg) from exc
        except json.JSONDecodeError as exc:
            msg = f"Certification pathways catalog is not valid JSON: {candidate}: {exc}"
            raise CertificationCatalogError(msg) from exc
        catalog = _parse_catalog(raw, candidate)
        trace_event("certification.catalog.loaded", path=candidate, ids=[pathway.id for pathway in catalog])
        return catalog

    searched = ", ".join(str(candidate) for candidate in candidates)
    msg = f"Certification pathways catalog was not found. Searched: {searched}"
    raise CertificationCatalogError(msg)


def validate_certification_pathways(
    show: Sequence[str],
    recommended: str | None,
    catalog: Sequence[CatalogPathway] | None = None,
) -> tuple[tuple[str, ...], str | None]:
    """Validate a project pathway selection while preserving its order."""
    normalized = tuple(show)
    if not normalized:
        raise ValueError("Select at least one certification pathway.")
    for pathway_id in normalized:
        if not isinstance(pathway_id, str) or not CERTIFICATION_PATHWAY_ID_RE.fullmatch(pathway_id):
            raise ValueError(f"Certification pathway ID must use kebab-case: {pathway_id!r}")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Certification pathways must be unique.")
    if recommended is not None:
        if not isinstance(recommended, str) or not CERTIFICATION_PATHWAY_ID_RE.fullmatch(recommended):
            raise ValueError(f"Recommended certification pathway ID must use kebab-case: {recommended!r}")
        if recommended not in normalized:
            raise ValueError("The recommended certification pathway must be included in the shown pathways.")
    if catalog is not None:
        catalog_ids = {pathway.id for pathway in catalog}
        unknown = [pathway_id for pathway_id in normalized if pathway_id not in catalog_ids]
        if unknown:
            raise ValueError(f"Unknown certification pathway ID(s): {', '.join(unknown)}")
    return normalized, recommended


def _certification_catalog_candidates(renderer_source: Path | None) -> tuple[Path, ...]:
    candidates: list[Path] = []
    env_path = os.environ.get(CERTIFICATION_CATALOG_ENV)
    if env_path:
        candidates.append(Path(env_path).expanduser())
    if renderer_source is not None:
        candidates.append(renderer_source.expanduser() / CERTIFICATION_CATALOG_RELATIVE_PATH)
    candidates.extend(
        workspace_root / "bt-web-report-template" / CERTIFICATION_CATALOG_RELATIVE_PATH
        for workspace_root in workspace_root_candidates()
    )
    candidates.append(app_support_dir() / "renderer" / "current" / CERTIFICATION_CATALOG_RELATIVE_PATH)
    return tuple(dict.fromkeys(candidates))


def _parse_catalog(raw: Any, source: Path) -> list[CatalogPathway]:
    if not isinstance(raw, list):
        raise CertificationCatalogError(f"Certification pathways catalog must be a JSON array: {source}")
    catalog: list[CatalogPathway] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise CertificationCatalogError(f"Certification catalog entry #{index + 1} must be an object: {source}")
        pathway_id = entry.get("id")
        title = entry.get("title")
        if not isinstance(pathway_id, str) or not CERTIFICATION_PATHWAY_ID_RE.fullmatch(pathway_id):
            raise CertificationCatalogError(
                f"Certification catalog entry #{index + 1} has an invalid kebab-case id: {pathway_id!r}"
            )
        if not isinstance(title, str) or not title.strip():
            raise CertificationCatalogError(f"Certification catalog entry {pathway_id!r} has no valid title.")
        if pathway_id in seen:
            raise CertificationCatalogError(f"Certification catalog contains duplicate id: {pathway_id}")
        seen.add(pathway_id)
        catalog.append(CatalogPathway(pathway_id, title.strip()))
    return catalog
