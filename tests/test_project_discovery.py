import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.projects import (
    _with_badges,
    discover_projects,
    read_project_status,
    set_project_phpp_path,
    validate_project_web_root,
)
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


def test_project_status_ignores_manager_lock_file(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "add", "project.yaml"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=project, check=True, capture_output=True)
    lock_dir = project / ".bldgtyp"
    lock_dir.mkdir()
    (lock_dir / "lock.yaml").write_text("user: ed\n")

    status = read_project_status(project, ManagerSettings(projects_root=tmp_path))

    assert status.git.is_repo
    assert status.git.dirty_count == 0


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


def test_set_project_phpp_path_writes_relative_project_yaml_path(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")
    replacement = tmp_path / "Project" / "PHPP" / "replacement.xlsm"
    replacement.parent.mkdir()
    replacement.write_text("fixture")

    written = set_project_phpp_path(project, replacement)

    raw = yaml.safe_load(written.read_text())
    assert raw["source_files"]["phpp_path"] == "../PHPP/replacement.xlsm"
    status = read_project_status(project, ManagerSettings(projects_root=tmp_path))
    assert status.metadata.phpp_path == replacement.resolve()


def test_set_project_phpp_path_rejects_non_workbook(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")
    not_workbook = tmp_path / "Project" / "07_PHPP" / "notes.txt"
    not_workbook.write_text("fixture")

    try:
        set_project_phpp_path(project, not_workbook)
    except ValueError as exc:
        assert ".xlsx or .xlsm" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_validate_project_web_root_requires_project_yaml(tmp_path: Path) -> None:
    project = _make_project(tmp_path / "Project" / "04_Web", "project")

    assert validate_project_web_root(project) == project.resolve()

    empty = tmp_path / "empty"
    empty.mkdir()
    try:
        validate_project_web_root(empty)
    except ValueError as exc:
        assert "project.yaml" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


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
