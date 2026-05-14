from pathlib import Path

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.settings import load_settings, save_settings, settings_write_status


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    settings = ManagerSettings(
        projects_root=tmp_path / "projects",
        extra_project_paths=(tmp_path / "extra",),
        btwr_executable="/tmp/btwr",
        renderer_source=tmp_path / "renderer",
        project_github_owner="bldgtyp-projects",
        lock_ttl_hours=2,
    )

    save_settings(settings, path)

    loaded = load_settings(path)
    assert loaded.projects_root == tmp_path / "projects"
    assert loaded.extra_project_paths == (tmp_path / "extra",)
    assert loaded.btwr_executable == "/tmp/btwr"
    assert loaded.renderer_source == tmp_path / "renderer"
    assert loaded.project_github_owner == "bldgtyp-projects"
    assert loaded.lock_ttl_hours == 2


def test_settings_write_status(tmp_path: Path) -> None:
    status = settings_write_status(tmp_path / "support")
    assert status.ok
