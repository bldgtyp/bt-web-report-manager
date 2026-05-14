from pathlib import Path

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.settings import (
    _default_btwr_executable,
    cleanup_project_runtime,
    load_settings,
    project_runtime_dirs,
    save_settings,
    settings_write_status,
    unhide_project_path,
    workspace_btwr_executable,
)


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    settings = ManagerSettings(
        projects_root=tmp_path / "projects",
        extra_project_paths=(tmp_path / "extra",),
        hidden_project_paths=(tmp_path / "projects" / "Archived" / "04_Web",),
        btwr_executable="/tmp/btwr",
        renderer_source=tmp_path / "renderer",
        project_github_owner="bldgtyp-projects",
        lock_ttl_hours=2,
    )

    save_settings(settings, path)

    loaded = load_settings(path)
    assert loaded.projects_root == tmp_path / "projects"
    assert loaded.extra_project_paths == (tmp_path / "extra",)
    assert loaded.hidden_project_paths == (tmp_path / "projects" / "Archived" / "04_Web",)
    assert loaded.btwr_executable == "/tmp/btwr"
    assert loaded.renderer_source == tmp_path / "renderer"
    assert loaded.project_github_owner == "bldgtyp-projects"
    assert loaded.lock_ttl_hours == 2


def test_settings_write_status(tmp_path: Path) -> None:
    status = settings_write_status(tmp_path / "support")
    assert status.ok


def test_project_runtime_dirs_match_cli_workspace_buckets(tmp_path: Path) -> None:
    assert project_runtime_dirs("project-2606", tmp_path / "support") == (
        tmp_path / "support" / "builds" / "project-2606",
        tmp_path / "support" / "previews" / "project-2606",
    )


def test_cleanup_project_runtime_removes_only_project_build_and_preview(tmp_path: Path) -> None:
    support = tmp_path / "support"
    build = support / "builds" / "project-2606"
    preview = support / "previews" / "project-2606"
    other_build = support / "builds" / "other"
    renderer = support / "renderer" / "current"
    for path in (build, preview, other_build, renderer):
        path.mkdir(parents=True)
        (path / "marker.txt").write_text("keep")

    removed = cleanup_project_runtime("project-2606", support)

    assert removed == (build, preview)
    assert not build.exists()
    assert not preview.exists()
    assert other_build.exists()
    assert renderer.exists()


def test_unhide_project_path_removes_matching_resolved_path(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "2606 29 Vandam St" / "04_Web"
    other = tmp_path / "projects" / "Archived" / "04_Web"
    settings = ManagerSettings(
        projects_root=tmp_path / "projects",
        hidden_project_paths=(project, other),
    )

    updated = unhide_project_path(settings, project)

    assert updated.hidden_project_paths == (other,)


def test_unhide_project_path_preserves_settings_when_path_is_visible(tmp_path: Path) -> None:
    hidden = tmp_path / "projects" / "Archived" / "04_Web"
    visible = tmp_path / "projects" / "2606 29 Vandam St" / "04_Web"
    settings = ManagerSettings(
        projects_root=tmp_path / "projects",
        hidden_project_paths=(hidden,),
        btwr_executable="/tmp/btwr",
        lock_ttl_hours=2,
    )

    updated = unhide_project_path(settings, visible)

    assert updated is settings


def test_missing_settings_uses_available_default_btwr(tmp_path: Path) -> None:
    loaded = load_settings(tmp_path / "missing.yaml")
    assert loaded.btwr_executable == _default_btwr_executable()


def test_workspace_btwr_executable_matches_default_when_present() -> None:
    workspace_btwr = workspace_btwr_executable()
    if workspace_btwr is not None:
        assert _default_btwr_executable() == workspace_btwr
