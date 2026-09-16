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

from bt_web_report_manager.certification_pathways import CatalogPathway
from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.projects import read_project_status
from bt_web_report_manager.ui.helpers import (
    action_card_states,
    badge_kind,
    badge_tooltip,
    certification_pathways_badge,
    certification_pathways_display,
    commit_disabled_reason,
    open_editor_disabled_reason,
    project_file_locations,
    project_metrics,
    project_row,
    report_access_badge,
    report_access_helper,
    report_access_warning,
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


def test_commit_disabled_for_dirty_repo_without_origin(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    (project / "content.mdx").write_text("draft\n")
    settings = ManagerSettings(projects_root=tmp_path)
    status = read_project_status(project, settings)

    reason = commit_disabled_reason(status, running=False, enabled=True)

    assert reason is not None
    assert "origin" in reason


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
    assert states["variables"].enabled
    assert states["build_pdf"].enabled
    assert states["build_pdf"].label == "Build PDF"
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


def test_report_access_helpers_label_public_and_otp_modes(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    public_status = read_project_status(project, settings)

    assert report_access_badge(public_status) == "Public, noindex"
    assert "search indexing disabled" in report_access_helper(public_status)

    raw = yaml.safe_load((project / "project.yaml").read_text())
    raw["publishing"] = {"access": {"mode": "cloudflare_access_otp", "allowed_emails": ["owner@example.com"]}}
    (project / "project.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    otp_status = read_project_status(project, settings)

    assert report_access_badge(otp_status) == "Gated by Cloudflare OTP"
    assert "email code" in report_access_helper(otp_status)
    assert "GitHub repo remains public" in report_access_warning()


def test_certification_pathway_helpers_label_default_and_unknown_ids(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path)
    default_status = read_project_status(project, settings)
    catalog = [
        CatalogPathway("phi-classic", "PHI Classic"),
        CatalogPathway("phi-leb", "PHI Low Energy Building"),
        CatalogPathway("phius-core-2024", "Phius CORE 2024"),
        CatalogPathway("phius-zero-2024", "Phius ZERO 2024"),
    ]

    assert certification_pathways_badge(default_status) == "Default"
    assert [item.title for item in certification_pathways_display(default_status, catalog)] == [
        pathway.title for pathway in catalog
    ]

    raw = yaml.safe_load((project / "project.yaml").read_text())
    raw["certification_pathways"] = {
        "show": ["future-pathway", "phi-classic"],
        "recommended": "future-pathway",
    }
    (project / "project.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    selected_status = read_project_status(project, settings)
    display = certification_pathways_display(selected_status, catalog)

    assert certification_pathways_badge(selected_status) == "2 selected"
    assert display[0].title == "future-pathway"
    assert display[0].unknown
    assert display[0].recommended


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
                "publishing": {"production_url": "https://sample.bldgtyp.com"},
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
