from pathlib import Path

import pytest

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.new_project import (
    NewProjectPlan,
    bootstrap_command,
    build_new_project_plan,
    clean_path_text,
    default_slug_from_project_folder,
    meaningful_existing_items,
    production_url_from_project_number,
    project_name_from_project_folder,
    project_number_from_project_folder,
    repo_name_from_number_name,
    sanitize_slug,
)


def test_build_new_project_plan_accepts_valid_inputs(tmp_path: Path) -> None:
    local_folder = tmp_path / "2606 29 Vandam St"
    target = local_folder / "04_Web"
    phpp = local_folder / "07_PHPP" / "model.xlsx"
    phpp.parent.mkdir(parents=True)
    phpp.write_text("fixture")

    plan = build_new_project_plan(
        project_title="2606 29 Vandam",
        project_number="2606",
        project_name="vandam",
        client_name="Client",
        building_name="29 Vandam St",
        phase="Design Analysis",
        local_folder=local_folder,
        target_web_path=target,
        phpp_path=phpp,
    )

    assert plan.project_number == "2606"
    assert plan.project_name == "vandam"
    assert plan.slug == "project-2606"
    assert plan.repo_name == "bt-proj-2606-vandam"
    assert plan.repo_owner == "bldgtyp-projects"
    assert plan.production_url == "https://project-2606.bldgtyp.com"
    checklist = "\n".join(plan.manual_checklist())
    assert "Phase 7 dependency" in checklist
    assert "bldgtyp-projects/bt-proj-2606-vandam" in checklist
    assert "content-only 04_Web" in checklist
    assert "Do not install Node dependencies" in checklist


def test_new_project_helpers_clean_paths_and_derive_names_from_project_folder() -> None:
    folder = "'/Users/em/Dropbox/bldgtyp/2606 29 Vandam St'"

    assert clean_path_text(folder) == "/Users/em/Dropbox/bldgtyp/2606 29 Vandam St"
    assert project_number_from_project_folder(folder) == "2606"
    assert project_name_from_project_folder(folder) == "vandam"
    assert default_slug_from_project_folder(folder) == "project-2606"
    assert sanitize_slug(" Manhattan Townhouse #29! ") == "manhattan-townhouse-29"
    assert repo_name_from_number_name("2606", "Vandam St") == "bt-proj-2606-vandam-st"
    assert production_url_from_project_number("2606") == "https://project-2606.bldgtyp.com"


def test_build_new_project_plan_sanitizes_slug_and_quoted_paths(tmp_path: Path) -> None:
    local_folder = tmp_path / "2606 29 Vandam St"
    target = local_folder / "04_Web"

    plan = build_new_project_plan(
        project_title="Project",
        project_number=" Project 2606!! ",
        project_name="29 Vandam St",
        client_name=None,
        building_name=None,
        phase=None,
        local_folder=f"'{local_folder}'",
        target_web_path=f"'{target}'",
        phpp_path=None,
    )

    assert plan.slug == "project-2606"
    assert plan.project_number == "2606"
    assert plan.project_name == "29-vandam-st"
    assert plan.repo_name == "bt-proj-2606-29-vandam-st"
    assert plan.local_folder == local_folder
    assert plan.target_web_path == target


def test_build_new_project_plan_ignores_ds_store_in_target(tmp_path: Path) -> None:
    local_folder = tmp_path / "2606 29 Vandam St"
    target = local_folder / "04_Web"
    target.mkdir(parents=True)
    (target / ".DS_Store").write_text("finder")

    plan = build_new_project_plan(
        project_title="Project",
        project_number="2606",
        project_name="vandam",
        client_name=None,
        building_name=None,
        phase=None,
        local_folder=local_folder,
        target_web_path=target,
        phpp_path=None,
    )

    assert plan.target_web_path == target
    assert meaningful_existing_items(target) == []


def test_build_new_project_plan_requires_overwrite_for_real_existing_content(tmp_path: Path) -> None:
    local_folder = tmp_path / "2606 29 Vandam St"
    target = local_folder / "04_Web"
    target.mkdir(parents=True)
    (target / "old.md").write_text("old")

    def build_plan(*, overwrite_existing: bool = False) -> NewProjectPlan:
        return build_new_project_plan(
            project_title="Project",
            project_number="2606",
            project_name="vandam",
            client_name=None,
            building_name=None,
            phase=None,
            local_folder=local_folder,
            target_web_path=target,
            phpp_path=None,
            overwrite_existing=overwrite_existing,
        )

    with pytest.raises(ValueError, match="not empty"):
        build_plan()

    plan = build_plan(overwrite_existing=True)

    assert plan.overwrite_existing


def test_build_new_project_plan_rejects_invalid_contract(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as exc:
        build_new_project_plan(
            project_title="Bad",
            project_number="26",
            project_name="Bad Slug",
            client_name=None,
            building_name=None,
            phase=None,
            local_folder=tmp_path / "Project",
            target_web_path=tmp_path / "Project" / "website",
            phpp_path=None,
        )

    message = str(exc.value)
    assert "must end in 04_Web" in message
    assert "Project number must be exactly 4 digits" in message


def test_bootstrap_command_matches_planned_btwr_new_arguments(tmp_path: Path) -> None:
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

    renderer = tmp_path / "renderer"
    spec = bootstrap_command(plan, ManagerSettings(btwr_executable="btwr-local", renderer_source=renderer))

    assert spec.name == "New project"
    assert spec.cwd == local_folder
    assert spec.refresh_on_success
    assert spec.args[:4] == ("btwr-local", "new", str(local_folder / "04_Web"), "--slug")
    assert ("--slug", "project-2606") == spec.args[3:5]
    assert ("--repo", "bt-proj-2606-vandam") == spec.args[7:9]
    assert ("--repo-owner", "bldgtyp-projects") == spec.args[9:11]
    assert ("--production-url", "https://project-2606.bldgtyp.com") == spec.args[11:13]
    assert "--production-url" in spec.args
    assert ("--renderer-source", str(renderer)) == spec.args[-2:]


def test_bootstrap_command_passes_overwrite_flag(tmp_path: Path) -> None:
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
        overwrite_existing=True,
    )

    spec = bootstrap_command(plan, ManagerSettings(btwr_executable="btwr-local"))

    assert "--overwrite" in spec.args
