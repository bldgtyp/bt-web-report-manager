from __future__ import annotations

import json
from pathlib import Path

import yaml

from bt_web_report_manager.project_variables import (
    ProjectVariable,
    normalize_project_variables,
    read_project_variables,
    write_project_variables,
)


def test_read_project_variables_seeds_template_fields_and_overlays_current_project_values(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        {
            "climate": {"weather_station_name": "NYC TMY3"},
            "mechanical": {"erv": {"manufacturer_name": "Zehnder"}},
            "user_defined": {"custom_added_by_user": "manual"},
        },
    )
    template_project_yaml = _make_template_project_yaml(
        tmp_path,
        {
            "certification": {"target": "Template target"},
            "climate": {"weather_station_name": "Template weather"},
            "mechanical": {"erv": {"manufacturer_name": "Template ERV"}},
        },
    )
    project_schema_json = _make_project_schema_json(
        tmp_path,
        {
            "CertificationNarrative": ["target"],
            "ClimateNarrative": ["weather_station_name"],
            "EnergyCodeNarrative": ["name"],
            "ErvNarrative": ["manufacturer_name"],
        },
    )

    variables = read_project_variables(
        project, template_project_yaml=template_project_yaml, project_schema_json=project_schema_json
    )

    assert variables == [
        ProjectVariable("narrative.certification.target", ""),
        ProjectVariable("narrative.climate.weather_station_name", "NYC TMY3"),
        ProjectVariable("narrative.energy_code.name", ""),
        ProjectVariable("narrative.mechanical.erv.manufacturer_name", "Zehnder"),
        ProjectVariable("narrative.user_defined.custom_added_by_user", "manual"),
    ]


def test_read_project_variables_falls_back_to_project_fields_when_template_is_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path, {"climate": {"weather_station_name": "NYC TMY3"}})

    variables = read_project_variables(
        project,
        template_project_yaml=tmp_path / "missing-project.yaml",
        project_schema_json=tmp_path / "missing-project.schema.json",
    )

    assert variables == [ProjectVariable("narrative.climate.weather_station_name", "NYC TMY3")]


def test_write_project_variables_updates_narrative_and_preserves_other_project_yaml_values(tmp_path: Path) -> None:
    project = _make_project(tmp_path, {"climate": {"weather_station_name": "Old"}})

    written = write_project_variables(
        project,
        [
            ProjectVariable("narrative.climate.weather_station_name", "New"),
            ProjectVariable("narrative.energy_code.ach_limit", "2.5 ACH50"),
            ProjectVariable("narrative.user_defined.cad_received_date", "May 1, 2026"),
        ],
    )

    raw = yaml.safe_load(written.read_text())
    assert raw["slug"] == "project-0000"
    assert raw["source_files"]["phpp_path"] == "../07_PHPP/model.xlsx"
    assert raw["narrative"] == {
        "climate": {"weather_station_name": "New"},
        "energy_code": {"ach_limit": "2.5 ACH50"},
        "user_defined": {"cad_received_date": "May 1, 2026"},
    }


def test_normalize_project_variables_rejects_names_outside_narrative() -> None:
    try:
        normalize_project_variables([("building.city", "Brooklyn")])
    except ValueError as exc:
        assert 'start with "narrative."' in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_normalize_project_variables_rejects_duplicate_names() -> None:
    try:
        normalize_project_variables(
            [
                ("narrative.climate.weather_station_name", "A"),
                ("narrative.climate.weather_station_name", "B"),
            ]
        )
    except ValueError as exc:
        assert "Duplicate variable name" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def _make_project(tmp_path: Path, narrative: dict[str, object]) -> Path:
    project = tmp_path / "Project" / "04_Web"
    project.mkdir(parents=True)
    _write_project_yaml(project / "project.yaml", narrative)
    return project


def _make_template_project_yaml(tmp_path: Path, narrative: dict[str, object]) -> Path:
    template = tmp_path / "template" / "project.yaml"
    template.parent.mkdir()
    _write_project_yaml(template, narrative)
    return template


def _make_project_schema_json(tmp_path: Path, defs: dict[str, list[str]]) -> Path:
    schema = tmp_path / "schema" / "project.schema.json"
    schema.parent.mkdir()
    schema.write_text(
        json.dumps(
            {
                "properties": {
                    "narrative": {
                        "properties": {
                            "certification": {"$ref": "#/$defs/CertificationNarrative"},
                            "climate": {"$ref": "#/$defs/ClimateNarrative"},
                            "energy_code": {"$ref": "#/$defs/EnergyCodeNarrative"},
                            "mechanical": {
                                "properties": {"erv": {"$ref": "#/$defs/ErvNarrative"}},
                            },
                        }
                    }
                },
                "$defs": {
                    name: {"properties": {field: {"anyOf": [{"type": "string"}, {"type": "null"}]} for field in fields}}
                    for name, fields in defs.items()
                },
            }
        )
    )
    return schema


def _write_project_yaml(path: Path, narrative: dict[str, object]) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.2.0",
                "slug": "project-0000",
                "project_title": "Project",
                "client_name": "Client",
                "building_name": "Building",
                "phase": "Design Analysis",
                "source_files": {"phpp_path": "../07_PHPP/model.xlsx", "data_dir": "data"},
                "narrative": narrative,
            },
            sort_keys=False,
        )
    )
