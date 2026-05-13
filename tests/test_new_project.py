from pathlib import Path

import pytest

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.new_project import bootstrap_command, build_new_project_plan


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
    assert plan.production_url == "https://2606-vandam.bldgtyp.com"
    assert "Phase 7 dependency" in "\n".join(plan.manual_checklist())


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
    assert "lowercase kebab-case" in message
    assert "must end in 04_Web" in message
    assert "Repo name must be bt-proj-Bad Slug" in message
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

    spec = bootstrap_command(plan, ManagerSettings(btwr_executable="btwr-local"))

    assert spec.name == "New project"
    assert spec.cwd == local_folder
    assert spec.refresh_on_success
    assert spec.args[:4] == ("btwr-local", "new", str(local_folder / "04_Web"), "--slug")
    assert "--production-url" in spec.args
