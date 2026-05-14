from pathlib import Path

import pytest

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.new_project import (
    bootstrap_command,
    build_new_project_plan,
    clean_path_text,
    default_slug_from_project_folder,
    production_url_from_slug,
    repo_name_from_slug,
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
        slug="2606-vandam",
        client_name="Client",
        building_name="29 Vandam St",
        phase="Design Analysis",
        local_folder=local_folder,
        target_web_path=target,
        phpp_path=phpp,
        repo_name="bt-proj-2606-vandam",
        production_url="https://2606-vandam.bldgtyp.com",
    )

    assert plan.slug == "2606-vandam"
    assert plan.repo_name == "bt-proj-2606-vandam"
    assert plan.repo_owner == "bldgtyp-projects"
    assert plan.production_url == "https://2606-vandam.bldgtyp.com"
    checklist = "\n".join(plan.manual_checklist())
    assert "Phase 7 dependency" in checklist
    assert "bldgtyp-projects/bt-proj-2606-vandam" in checklist
    assert "content-only 04_Web" in checklist
    assert "Do not install Node dependencies" in checklist


def test_new_project_helpers_clean_paths_and_derive_bt_number_slug() -> None:
    folder = "'/Users/em/Dropbox/bldgtyp/2606 29 Vandam St'"

    assert clean_path_text(folder) == "/Users/em/Dropbox/bldgtyp/2606 29 Vandam St"
    assert default_slug_from_project_folder(folder) == "project-2606"
    assert sanitize_slug(" Manhattan Townhouse #29! ") == "manhattan-townhouse-29"
    assert repo_name_from_slug("manhattan-townhouse-29") == "bt-proj-manhattan-townhouse-29"
    assert production_url_from_slug("manhattan-townhouse-29") == "https://manhattan-townhouse-29.bldgtyp.com"


def test_build_new_project_plan_sanitizes_slug_and_quoted_paths(tmp_path: Path) -> None:
    local_folder = tmp_path / "2606 29 Vandam St"
    target = local_folder / "04_Web"

    plan = build_new_project_plan(
        project_title="Project",
        slug=" Project 2606!! ",
        client_name=None,
        building_name=None,
        phase=None,
        local_folder=f"'{local_folder}'",
        target_web_path=f"'{target}'",
        phpp_path=None,
        repo_name="bt-proj-project-2606",
        production_url="https://project-2606.bldgtyp.com",
    )

    assert plan.slug == "project-2606"
    assert plan.local_folder == local_folder
    assert plan.target_web_path == target


def test_build_new_project_plan_rejects_invalid_contract(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as exc:
        build_new_project_plan(
            project_title="Bad",
            slug="Bad Slug",
            client_name=None,
            building_name=None,
            phase=None,
            local_folder=tmp_path / "Project",
            target_web_path=tmp_path / "Project" / "website",
            phpp_path=None,
            repo_name="custom-repo",
            production_url="http://example.com/report",
        )

    message = str(exc.value)
    assert "must end in 04_Web" in message
    assert "Repo name must be bt-proj-bad-slug" in message
    assert "https origin URL" in message


def test_bootstrap_command_matches_planned_btwr_new_arguments(tmp_path: Path) -> None:
    local_folder = tmp_path / "Project"
    plan = build_new_project_plan(
        project_title="Project",
        slug="project",
        client_name=None,
        building_name=None,
        phase=None,
        local_folder=local_folder,
        target_web_path=local_folder / "04_Web",
        phpp_path=None,
        repo_name="bt-proj-project",
        production_url="https://project.bldgtyp.com",
    )

    renderer = tmp_path / "renderer"
    spec = bootstrap_command(plan, ManagerSettings(btwr_executable="btwr-local", renderer_source=renderer))

    assert spec.name == "New project"
    assert spec.cwd == local_folder
    assert spec.refresh_on_success
    assert spec.args[:4] == ("btwr-local", "new", str(local_folder / "04_Web"), "--slug")
    assert "--production-url" in spec.args
    assert ("--renderer-source", str(renderer)) == spec.args[-2:]
