"""Tests for the pure helpers that drive the status tab.

The actual rendering layer was rewritten to NiceGUI; the helpers were
extracted to ``ui/helpers.py`` so they can be tested without booting a
browser. These tests cover the per-action disabled-reason contract and the
status-explanations text.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.projects import read_project_status
from bt_web_report_manager.ui.helpers import (
    action_card_states,
    badge_kind,
    badge_tooltip,
    commit_disabled_reason,
    open_editor_disabled_reason,
    project_file_locations,
    project_metrics,
    project_row,
    scrape_disabled_reason,
    selected_disabled_reason,
    status_explanations,
)


def test_scrape_enabled_when_phpp_is_present(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    assert scrape_disabled_reason(status, running=False, enabled=True) is None


def test_scrape_disabled_when_phpp_is_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=False)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    reason = scrape_disabled_reason(status, running=False, enabled=True)
    assert reason is not None
    assert "PHPP workbook" in reason


def test_commit_disabled_for_clean_repo(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    reason = commit_disabled_reason(status, running=False, enabled=True)
    assert reason is not None
    assert "clean" in reason


def test_open_editor_enabled_for_content_only_project(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    assert open_editor_disabled_reason(status, running=False, enabled=True) is None


def test_status_explanations_call_out_needed_scrape(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    lines = status_explanations(status)
    assert any("No data manifest" in line for line in lines)


def test_selected_disabled_reason_without_selection() -> None:
    assert selected_disabled_reason(None, running=False, enabled=False) == "Disabled: no project selected."


def test_project_metrics_count_portfolio_status(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    metrics = {metric.label: metric.value for metric in project_metrics([status])}

    assert metrics == {"Projects": 1, "Dirty git": 0, "Need scrape": 1, "Warnings": 0}


def test_project_row_keeps_current_table_contract(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    row = project_row(status)

    assert row["name"] == "Sample Project"
    assert row["slug"] == "sample"
    assert row["client_building"] == "Client / Building"
    assert "No data" in row["badges"]
    assert 'class="chip chip-danger"' in row["badges_html"]


def test_badge_kind_classifies_semantic_states() -> None:
    assert badge_kind("Data current") == "success"
    assert badge_kind("Dirty (2)") == "warning"
    assert badge_kind("Locked by you") == "accent"
    assert badge_kind("No git") == "danger"


def test_dirty_badge_tooltip_explains_git_count() -> None:
    tooltip = badge_tooltip("Dirty (10)")

    assert "Git worktree has uncommitted changes" in tooltip
    assert "staged, unstaged, and untracked" in tooltip


def test_action_card_states_preserve_disabled_reasons(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    states = action_card_states(status, running=False, enabled=True)

    assert states["scrape"].enabled
    assert states["commit"].enabled is False
    assert "clean" in states["commit"].tooltip


def test_project_file_locations_include_expected_workspace_paths(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    locations = {location.key: location for location in project_file_locations(status)}

    assert locations["web_root"].path == project
    assert locations["phpp"].kind == "XLSX"
    assert locations["manifest"].value.endswith("data/manifest.json")


def test_project_file_locations_include_unconfigured_phpp(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=False)
    raw = yaml.safe_load((project / "project.yaml").read_text())
    raw["source_files"]["phpp_path"] = ""
    (project / "project.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    locations = {location.key: location for location in project_file_locations(status)}

    assert locations["phpp"].value == "Not configured"
    assert locations["phpp"].path is None


def _make_project(tmp_path: Path, *, with_phpp: bool) -> Path:
    project = tmp_path / "Sample Project" / "04_Web"
    phpp = tmp_path / "Sample Project" / "07_PHPP" / "model.xlsx"
    project.mkdir(parents=True)
    phpp.parent.mkdir()
    if with_phpp:
        phpp.write_text("fixture")
    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": "sample",
                "project_title": "Sample Project",
                "client_name": "Client",
                "building_name": "Building",
                "phase": "Design",
                "source_files": {"phpp_path": "../07_PHPP/model.xlsx", "data_dir": "data"},
            },
            sort_keys=False,
        )
    )
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "add", "project.yaml"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=project, check=True, capture_output=True)
    return project
