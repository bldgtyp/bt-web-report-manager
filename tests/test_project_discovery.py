import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.projects import _with_badges, discover_projects, read_project_status
from bt_web_report_manager.models import GitStatus, LockInfo, ProjectMetadata, ProjectStatus


def test_discover_standard_and_extra_project_paths(tmp_path: Path) -> None:
    standard = _make_project(tmp_path / "projects" / "Project A" / "04_Web", "project-a")
    extra = _make_project(tmp_path / "elsewhere" / "04_Web_next", "project-b")
    settings = ManagerSettings(projects_root=tmp_path / "projects", extra_project_paths=(extra,))

    statuses = discover_projects(settings)

    assert [status.project_path for status in statuses] == [standard, extra]
    assert [status.metadata.slug for status in statuses] == ["project-a", "project-b"]


def test_discover_projects_skips_hidden_project_paths(tmp_path: Path) -> None:
    visible = _make_project(tmp_path / "projects" / "Project A" / "04_Web", "project-a")
    hidden = _make_project(tmp_path / "projects" / "Project B" / "04_Web", "project-b")
    settings = ManagerSettings(projects_root=tmp_path / "projects", hidden_project_paths=(hidden,))

    statuses = discover_projects(settings)

    assert [status.project_path for status in statuses] == [visible]
    assert [status.metadata.slug for status in statuses] == ["project-a"]


def test_project_status_detects_no_data_and_git_dirty(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    (project / "notes.md").write_text("dirty")

    status = read_project_status(project, ManagerSettings(projects_root=tmp_path))

    assert status.needs_scrape
    assert "No data" in status.badges
    assert status.git.is_repo
    assert status.git.dirty_count == 2


def test_project_status_uses_manifest_generated_at(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")
    data = project / "data"
    data.mkdir()
    (data / "manifest.json").write_text(json.dumps({"generated_at": "2099-01-01T00:00:00Z"}))

    status = read_project_status(project, ManagerSettings(projects_root=tmp_path))

    assert not status.needs_scrape
    assert status.manifest_generated_at == datetime(2099, 1, 1, tzinfo=timezone.utc)
    assert "Data current" in status.badges


def test_pending_starter_manifest_requires_scrape_without_warning(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")
    data = project / "data"
    data.mkdir()
    (data / "manifest.json").write_text(json.dumps({"status": "pending", "variants": []}))

    status = read_project_status(project, ManagerSettings(projects_root=tmp_path))

    assert status.manifest_generated_at is None
    assert status.needs_scrape
    assert "Needs scrape" in status.badges
    assert status.warnings == ()


def test_manifest_without_generated_at_warns_when_not_pending(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")
    data = project / "data"
    data.mkdir()
    (data / "manifest.json").write_text(json.dumps({"variants": []}))

    status = read_project_status(project, ManagerSettings(projects_root=tmp_path))

    assert "manifest.json has no generated_at timestamp" in status.warnings


def test_lock_badge_reports_stale_lock(tmp_path: Path) -> None:
    now = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    status = ProjectStatus(
        project_path=tmp_path,
        metadata=ProjectMetadata("slug", "Project", None, None, None, None, tmp_path / "data", None),
        git=GitStatus(False),
        lock=LockInfo(path=tmp_path / ".bldgtyp" / "lock.yaml", user="ed", expires_at=now - timedelta(minutes=1)),
    )

    with_badges = _with_badges(status, now=now)

    assert "Stale lock" in with_badges.badges


def _make_project(path: Path, slug: str) -> Path:
    path.mkdir(parents=True)
    phpp = path.parent / "07_PHPP" / "model.xlsx"
    phpp.parent.mkdir()
    phpp.write_text("fixture")
    (path / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": slug,
                "project_title": f"{slug} title",
                "client_name": "Client",
                "phase": "Design",
                "source_files": {"phpp_path": "../07_PHPP/model.xlsx", "data_dir": "data"},
                "publishing": {"production_url": f"https://{slug}.bldgtyp.com"},
            }
        )
    )
    return path
