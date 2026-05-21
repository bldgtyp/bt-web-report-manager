from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests

from bt_web_report_manager import deletion
from bt_web_report_manager.deletion import (
    DeleteStepResult,
    build_project_delete_plan,
    delete_project_artifacts,
    format_project_delete_confirmation,
    github_repo_from_remote,
)
from bt_web_report_manager.models import GitStatus, ManagerSettings, ProjectMetadata, ProjectStatus


def test_github_repo_from_remote_parses_github_urls() -> None:
    assert github_repo_from_remote("https://github.com/bldgtyp-projects/bt-proj-2606-vandam.git") == (
        "bldgtyp-projects/bt-proj-2606-vandam"
    )
    assert github_repo_from_remote("git@github.com:bldgtyp-projects/bt-proj-2606-vandam.git") == (
        "bldgtyp-projects/bt-proj-2606-vandam"
    )
    assert github_repo_from_remote("ssh://git@github.com/bldgtyp-projects/bt-proj-2606-vandam.git") == (
        "bldgtyp-projects/bt-proj-2606-vandam"
    )
    assert github_repo_from_remote("/tmp/local.git") is None


def test_delete_plan_lists_full_cleanup_resources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    support = tmp_path / "support"
    monkeypatch.setenv("BTWR_MANAGER_APP_SUPPORT", str(support))
    project = _project_status(tmp_path)

    plan = build_project_delete_plan(project)

    assert plan.github_repo == "bldgtyp-projects/bt-proj-2606-vandam"
    assert plan.cloudflare_pages_project == "bt-proj-2606-vandam"
    assert plan.cloudflare_custom_domain == "project-2606.bldgtyp.com"
    assert plan.runtime_dirs == (support / "builds" / "project-2606", support / "previews" / "project-2606")
    message = format_project_delete_confirmation(plan)
    assert "Local report folder" in message
    assert "GitHub repository: bldgtyp-projects/bt-proj-2606-vandam" in message
    assert "Cloudflare custom domains: project-2606.bldgtyp.com" in message
    assert "Cloudflare Pages project: bt-proj-2606-vandam" in message
    assert "PHPP workbook" in message


def test_delete_project_artifacts_removes_remote_before_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    support = tmp_path / "support"
    monkeypatch.setenv("BTWR_MANAGER_APP_SUPPORT", str(support))
    project = _project_status(tmp_path)
    for runtime_dir in (support / "builds" / "project-2606", support / "previews" / "project-2606"):
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "marker.txt").write_text("runtime")
    plan = build_project_delete_plan(project)
    calls: list[str] = []

    def fake_delete_cloudflare_pages(
        *, pages_project: str, custom_domain: str | None, settings: ManagerSettings
    ) -> tuple[DeleteStepResult, ...]:
        calls.append(f"cloudflare:{pages_project}:{custom_domain}")
        return (DeleteStepResult("Cloudflare Pages project", True, "deleted"),)

    def fake_delete_github_repo(repo: str, settings: ManagerSettings) -> DeleteStepResult:
        calls.append(f"github:{repo}")
        return DeleteStepResult("GitHub repository", True, "deleted")

    monkeypatch.setattr(deletion, "delete_cloudflare_pages", fake_delete_cloudflare_pages)
    monkeypatch.setattr(deletion, "delete_github_repo", fake_delete_github_repo)

    result = delete_project_artifacts(plan, ManagerSettings())

    assert result.ok
    assert calls == [
        "cloudflare:bt-proj-2606-vandam:project-2606.bldgtyp.com",
        "github:bldgtyp-projects/bt-proj-2606-vandam",
    ]
    assert not project.project_path.exists()
    assert result.removed_runtime_dirs == (support / "builds" / "project-2606", support / "previews" / "project-2606")


def test_delete_project_artifacts_halts_on_remote_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BTWR_MANAGER_APP_SUPPORT", str(tmp_path / "support"))
    project = _project_status(tmp_path)
    plan = build_project_delete_plan(project)

    def fake_delete_cloudflare_pages(
        *, pages_project: str, custom_domain: str | None, settings: ManagerSettings
    ) -> tuple[DeleteStepResult, ...]:
        return (DeleteStepResult("Cloudflare Pages project", False, "blocked"),)

    monkeypatch.setattr(deletion, "delete_cloudflare_pages", fake_delete_cloudflare_pages)

    result = delete_project_artifacts(plan, ManagerSettings())

    assert not result.ok
    assert project.project_path.exists()


def test_delete_cloudflare_pages_detaches_all_reported_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account")
    deleted_urls: list[str] = []

    class Response:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload
            self.ok = 200 <= status_code < 300
            self.text = str(payload)

        def json(self) -> dict[str, Any]:
            return self._payload

    def fake_get(url: str, **kwargs: Any) -> Response:
        assert "/pages/projects/bt-proj/domains" in url
        return Response(
            200,
            {
                "success": True,
                "result": [
                    {"name": "project-2606.bldgtyp.com"},
                    {"name": "alias-2606.bldgtyp.com"},
                ],
            },
        )

    def fake_delete(url: str, **kwargs: Any) -> Response:
        deleted_urls.append(url)
        return Response(200, {"success": True})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "delete", fake_delete)

    result = deletion.delete_cloudflare_pages(
        pages_project="bt-proj",
        custom_domain="project-2606.bldgtyp.com",
        settings=ManagerSettings(),
    )

    assert all(step.ok for step in result)
    assert deleted_urls == [
        "https://api.cloudflare.com/client/v4/accounts/account/pages/projects/bt-proj/domains/alias-2606.bldgtyp.com",
        "https://api.cloudflare.com/client/v4/accounts/account/pages/projects/bt-proj/domains/project-2606.bldgtyp.com",
        "https://api.cloudflare.com/client/v4/accounts/account/pages/projects/bt-proj",
    ]


def _project_status(tmp_path: Path) -> ProjectStatus:
    project_path = tmp_path / "2606 29 Vandam St" / "04_Web"
    project_path.mkdir(parents=True)
    (project_path / "project.yaml").write_text(
        "\n".join(
            [
                "slug: project-2606",
                "project_title: Vandam",
                "source_files:",
                "  data_dir: data",
                "publishing:",
                "  production_url: https://project-2606.bldgtyp.com",
                "  cloudflare_pages_project: bt-proj-2606-vandam",
                "",
            ]
        )
    )
    return ProjectStatus(
        project_path=project_path,
        metadata=ProjectMetadata(
            "project-2606",
            "Vandam",
            None,
            None,
            None,
            tmp_path / "2606 29 Vandam St" / "PHPP.xlsx",
            project_path / "data",
            "https://project-2606.bldgtyp.com",
        ),
        git=GitStatus(
            True,
            branch="main",
            dirty_count=0,
            remote="https://github.com/bldgtyp-projects/bt-proj-2606-vandam.git",
        ),
    )
