from __future__ import annotations

from pathlib import Path

import yaml

from bt_web_report_manager.project_variables import (
    ProjectVariable,
    normalize_project_variables,
    read_project_variables,
    write_project_variables,
)


def test_read_project_variables_loads_current_project_yaml_fields(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        {
            "climate": {"weather_station_name": "NYC TMY3", "custom_added_by_user": "manual"},
            "mechanical": {"erv": {"manufacturer_name": "Zehnder"}},
        },
    )

    variables = read_project_variables(project)

    assert variables == [
        ProjectVariable("narrative.climate.weather_station_name", "NYC TMY3"),
        ProjectVariable("narrative.climate.custom_added_by_user", "manual"),
        ProjectVariable("narrative.mechanical.erv.manufacturer_name", "Zehnder"),
    ]


def test_write_project_variables_updates_narrative_and_preserves_other_project_yaml_values(tmp_path: Path) -> None:
    project = _make_project(tmp_path, {"climate": {"weather_station_name": "Old"}})

    written = write_project_variables(
        project,
        [
            ProjectVariable("narrative.climate.weather_station_name", "New"),
            ProjectVariable("narrative.energy_code.ach_limit", "2.5 ACH50"),
        ],
    )

    raw = yaml.safe_load(written.read_text())
    assert raw["slug"] == "project-0000"
    assert raw["source_files"]["phpp_path"] == "../07_PHPP/model.xlsx"
    assert raw["narrative"] == {
        "climate": {"weather_station_name": "New"},
        "energy_code": {"ach_limit": "2.5 ACH50"},
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
    (project / "project.yaml").write_text(
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
    return project
