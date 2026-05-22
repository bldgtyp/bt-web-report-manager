"""Read and write prose-facing variables in a project's ``project.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import yaml

from bt_web_report_manager.settings import app_support_dir
from bt_web_report_manager.trace import trace_event

VARIABLE_ROOT = "narrative"
USER_DEFINED_VARIABLE_ROOT = f"{VARIABLE_ROOT}.user_defined"
TEMPLATE_PROJECT_YAML_ENV = "BTWR_MANAGER_TEMPLATE_PROJECT_YAML"
PROJECT_SCHEMA_JSON_ENV = "BTWR_MANAGER_PROJECT_SCHEMA_JSON"


@dataclass(frozen=True)
class ProjectVariable:
    key: str
    value: str


def read_project_variables(
    project_path: Path,
    template_project_yaml: Path | None = None,
    project_schema_json: Path | None = None,
) -> list[ProjectVariable]:
    """Return template-seeded ``narrative.*`` variable leaves for a project."""
    project_yaml = project_path / "project.yaml"
    schema_variables = _schema_variable_keys(project_schema_json)
    template_variables = _template_variable_keys(template_project_yaml)
    project_variables = _read_project_yaml_variables(project_yaml)
    variables = _merge_variable_layers(schema_variables, template_variables, project_variables)
    trace_event(
        "projects.variables.read",
        project_path=project_path,
        project_yaml=project_yaml,
        template_project_yaml=template_project_yaml,
        project_schema_json=project_schema_json,
        keys=[variable.key for variable in variables],
    )
    return variables


def write_project_variables(project_path: Path, variables: list[ProjectVariable]) -> Path:
    """Replace the ``narrative`` variable tree in ``project.yaml`` from form rows."""
    project_yaml = project_path / "project.yaml"
    raw = _read_project_yaml(project_yaml)
    normalized = normalize_project_variables([(variable.key, variable.value) for variable in variables])
    raw[VARIABLE_ROOT] = _variables_to_nested_mapping(normalized)
    project_yaml.write_text(yaml.safe_dump(raw, sort_keys=False))
    trace_event(
        "projects.variables.write",
        project_path=project_path,
        project_yaml=project_yaml,
        keys=[variable.key for variable in normalized],
    )
    return project_yaml


def normalize_project_variables(rows: list[tuple[str, str]]) -> list[ProjectVariable]:
    """Validate and normalize form rows into project variable records."""
    out: list[ProjectVariable] = []
    seen: set[str] = set()
    for raw_key, raw_value in rows:
        key = _normalize_variable_key(raw_key)
        if key in seen:
            msg = f"Duplicate variable name: {key}"
            raise ValueError(msg)
        seen.add(key)
        out.append(ProjectVariable(key=key, value=raw_value))
    return out


def _read_project_yaml_variables(project_yaml: Path) -> list[ProjectVariable]:
    raw = _read_project_yaml(project_yaml)
    narrative = raw.get(VARIABLE_ROOT) or {}
    if not isinstance(narrative, dict):
        msg = f"{VARIABLE_ROOT} must be a mapping in {project_yaml}"
        raise ValueError(msg)
    return [
        ProjectVariable(f"{VARIABLE_ROOT}.{'.'.join(path)}", _variable_value_to_string(value))
        for path, value in _flatten_variable_leaves(narrative)
    ]


def _template_variable_keys(template_project_yaml: Path | None) -> list[ProjectVariable]:
    path = template_project_yaml or _default_template_project_yaml()
    if path is None:
        trace_event("projects.variables.template_missing")
        return []
    try:
        variables = _read_project_yaml_variables(path)
    except (OSError, ValueError) as exc:
        trace_event("projects.variables.template_read_failed", path=path, error=str(exc))
        return []
    return [ProjectVariable(variable.key, "") for variable in variables]


def _schema_variable_keys(project_schema_json: Path | None) -> list[ProjectVariable]:
    path = project_schema_json or _default_project_schema_json()
    if path is None:
        trace_event("projects.variables.schema_missing")
        return []
    try:
        raw = json.loads(path.read_text())
        root_properties = raw.get("properties")
        if not isinstance(root_properties, dict) or not isinstance(root_properties.get(VARIABLE_ROOT), dict):
            msg = f"Project schema is missing properties.{VARIABLE_ROOT}."
            raise ValueError(msg)
        variables = [
            ProjectVariable(".".join(path_parts), "")
            for path_parts in _schema_string_leaves(raw, root_properties[VARIABLE_ROOT], (VARIABLE_ROOT,))
        ]
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        trace_event("projects.variables.schema_read_failed", path=path, error=str(exc))
        return []
    trace_event("projects.variables.schema_read", path=path, keys=[variable.key for variable in variables])
    return variables


def _default_project_schema_json() -> Path | None:
    for candidate in _project_schema_json_candidates():
        if candidate.exists():
            trace_event("projects.variables.schema_found", path=candidate)
            return candidate
        trace_event("projects.variables.schema_candidate_missing", path=candidate)
    return None


def _project_schema_json_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    env_path = os.environ.get(PROJECT_SCHEMA_JSON_ENV)
    if env_path:
        candidates.append(Path(env_path).expanduser())
    workspace_root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            workspace_root / "bt-web-report-schemas" / "schemas" / "project.schema.json",
            app_support_dir()
            / "renderer"
            / "current"
            / "node_modules"
            / "@bldgtyp"
            / "web-report-schemas"
            / "schemas"
            / "project.schema.json",
            Path(
                "~/Dropbox/bldgtyp-00/00_PH_Tools/bt-web-report/bt-web-report-schemas/schemas/project.schema.json"
            ).expanduser(),
        ]
    )
    return tuple(dict.fromkeys(candidates))


def _schema_string_leaves(
    root_schema: dict[str, Any],
    node: dict[str, Any],
    path_parts: tuple[str, ...],
) -> list[tuple[str, ...]]:
    expanded = _resolve_schema_ref(root_schema, node)
    properties = expanded.get("properties")
    if not isinstance(properties, dict):
        return []

    leaves: list[tuple[str, ...]] = []
    for name, child in properties.items():
        if not isinstance(child, dict):
            continue
        child_path = (*path_parts, str(name))
        if _is_schema_string_leaf(child):
            leaves.append(child_path)
            continue
        leaves.extend(_schema_string_leaves(root_schema, child, child_path))
    return leaves


def _resolve_schema_ref(root_schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        msg = f"Unsupported project schema ref: {ref}"
        raise ValueError(msg)
    defs = root_schema.get("$defs")
    if not isinstance(defs, dict):
        msg = "Project schema is missing $defs."
        raise ValueError(msg)
    target = defs.get(ref.removeprefix(prefix))
    if not isinstance(target, dict):
        msg = f"Project schema ref not found: {ref}"
        raise ValueError(msg)
    return target


def _is_schema_string_leaf(node: dict[str, Any]) -> bool:
    if "const" in node:
        return False
    node_type = node.get("type")
    if node_type == "string":
        return True
    if isinstance(node_type, list) and "string" in node_type:
        return True
    any_of = node.get("anyOf")
    return isinstance(any_of, list) and any(
        isinstance(option, dict) and option.get("type") == "string" and "const" not in option for option in any_of
    )


def _default_template_project_yaml() -> Path | None:
    for candidate in _template_project_yaml_candidates():
        if candidate.exists():
            trace_event("projects.variables.template_found", path=candidate)
            return candidate
        trace_event("projects.variables.template_candidate_missing", path=candidate)
    return None


def _template_project_yaml_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    env_path = os.environ.get(TEMPLATE_PROJECT_YAML_ENV)
    if env_path:
        candidates.append(Path(env_path).expanduser())
    workspace_root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            workspace_root / "bt-web-report-template" / "project.yaml",
            app_support_dir() / "renderer" / "current" / "project.yaml",
            Path("~/Dropbox/bldgtyp-00/00_PH_Tools/bt-web-report/bt-web-report-template/project.yaml").expanduser(),
        ]
    )
    return tuple(dict.fromkeys(candidates))


def _merge_variable_layers(
    *layers: list[ProjectVariable],
) -> list[ProjectVariable]:
    values_by_key: dict[str, str] = {}
    ordered_keys: list[str] = []
    for layer in layers:
        for variable in layer:
            if variable.key not in values_by_key:
                ordered_keys.append(variable.key)
            values_by_key[variable.key] = variable.value
    return [ProjectVariable(key, values_by_key[key]) for key in ordered_keys]


def _read_project_yaml(project_yaml: Path) -> dict[str, Any]:
    if not project_yaml.exists():
        msg = f"project.yaml does not exist: {project_yaml}"
        raise ValueError(msg)
    raw = yaml.safe_load(project_yaml.read_text()) or {}
    if not isinstance(raw, dict):
        msg = f"project.yaml must contain a mapping: {project_yaml}"
        raise ValueError(msg)
    return raw


def _flatten_variable_leaves(value: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    leaves: list[tuple[tuple[str, ...], Any]] = []
    for key, child in value.items():
        path = (*prefix, str(key))
        if isinstance(child, dict):
            leaves.extend(_flatten_variable_leaves(child, path))
        else:
            leaves.append((path, child))
    return leaves


def _variable_value_to_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _variables_to_nested_mapping(variables: list[ProjectVariable]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for variable in variables:
        parts = variable.key.split(".")
        branch = root
        for part in parts[1:-1]:
            existing = branch.get(part)
            if existing is None:
                existing = {}
                branch[part] = existing
            if not isinstance(existing, dict):
                msg = f"Variable name collides with scalar value: {variable.key}"
                raise ValueError(msg)
            branch = existing
        branch[parts[-1]] = variable.value
    return root


def _normalize_variable_key(value: str) -> str:
    key = value.strip()
    if not key:
        msg = "Variable name is required."
        raise ValueError(msg)
    if key == VARIABLE_ROOT or not key.startswith(f"{VARIABLE_ROOT}."):
        msg = f'Variable name must start with "{VARIABLE_ROOT}.".'
        raise ValueError(msg)
    parts = key.split(".")
    if any(part == "" for part in parts):
        msg = f"Variable name has an empty segment: {key}"
        raise ValueError(msg)
    for part in parts:
        if not _is_valid_key_part(part):
            msg = f"Variable name segment must use letters, numbers, and underscores: {part}"
            raise ValueError(msg)
    return ".".join(parts)


def _is_valid_key_part(value: str) -> bool:
    first = value[0]
    if not (first.isalpha() or first == "_"):
        return False
    return all(char.isalnum() or char == "_" for char in value)
