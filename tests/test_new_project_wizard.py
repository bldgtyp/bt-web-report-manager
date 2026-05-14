"""Tests for the new-project wizard's plan + manual-checklist behaviour.

The wizard's UI rendering now lives in ``ui/new_project.py`` (NiceGUI) and
needs a browser to drive. The plan/checklist logic itself was already in
``new_project.py`` (un-changed) and is the load-bearing part — these tests
exercise that surface directly.
"""

from __future__ import annotations

from pathlib import Path

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.new_project import (
    bootstrap_command_available,
    bootstrap_command_status,
    build_new_project_plan,
)


def test_build_new_project_plan_produces_summary_and_manual_checklist(tmp_path: Path) -> None:
    local_folder = tmp_path / "Project"
    plan = build_new_project_plan(
        project_title="Project",
        project_number="2606",
        project_name="vandam",
        client_name=None,
        building_name=None,
        phase=None,
        local_folder=local_folder,
        target_web_path=local_folder / "04_Web",
        phpp_path=None,
    )

    summary = plan.summary_lines()
    checklist = plan.manual_checklist()

    assert any("Project title: Project" in line for line in summary)
    assert any("GitHub repo: bldgtyp-projects/bt-proj-2606-vandam" in line for line in summary)
    assert any("Phase 7 dependency: btwr new is not available" in line for line in checklist)
    assert any(f"Create target web folder: {local_folder / '04_Web'}" in line for line in checklist)


def test_bootstrap_command_available_returns_false_for_missing_btwr(tmp_path: Path) -> None:
    settings = ManagerSettings(
        projects_root=tmp_path,
        btwr_executable="btwr-missing-for-new-project-test",
    )
    assert bootstrap_command_available(settings) is False
    status = bootstrap_command_status(settings)
    assert not status.available
    assert "not found" in status.message
