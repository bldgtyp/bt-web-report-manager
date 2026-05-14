from pathlib import Path

from bt_web_report_manager.models import ManagerSettings, ToolStatus
from bt_web_report_manager.support import path_status, renderer_status, support_summary


def test_path_status_reports_missing_path(tmp_path: Path) -> None:
    status = path_status("projects_root", tmp_path / "missing", require_dir=True, writable=False)

    assert not status.ok
    assert status.path is None
    assert "does not exist" in status.message


def test_path_status_reports_existing_folder(tmp_path: Path) -> None:
    status = path_status("projects_root", tmp_path, require_dir=True, writable=False)

    assert status.ok
    assert status.path == str(tmp_path)
    assert status.message == "folder exists"


def test_renderer_status_accepts_default_renderer() -> None:
    status = renderer_status(None)

    assert status.ok
    assert status.executable == "default"
    assert "default renderer" in status.message


def test_support_summary_includes_settings_and_statuses(tmp_path: Path) -> None:
    settings = ManagerSettings(
        projects_root=tmp_path / "projects",
        hidden_project_paths=(tmp_path / "hidden" / "04_Web",),
        renderer_source=tmp_path / "renderer",
    )
    statuses = [ToolStatus("pnpm", "pnpm", "/opt/homebrew/bin/pnpm", "10.0.0", True, "10.0.0")]

    summary = support_summary(settings, statuses)

    assert "bt-web-report Manager support summary" in summary
    assert f"projects_root: {tmp_path / 'projects'}" in summary
    assert f"renderer_source: {tmp_path / 'renderer'}" in summary
    assert "OK pnpm" in summary
