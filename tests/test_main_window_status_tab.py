import os
import subprocess
from pathlib import Path

import yaml
from PySide6.QtWidgets import QApplication

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.projects import read_project_status
from bt_web_report_manager.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_status_tab_shows_full_mvp_status_contract(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=True)
    settings = ManagerSettings(projects_root=tmp_path, github_owner="example", github_repo="manager")
    window = MainWindow(settings, [read_project_status(project, settings)])
    window.table.selectRow(0)
    _app().processEvents()

    assert window.table.columnCount() == 10
    assert "1 projects" in window.summary.text()
    assert "1 need scrape" in window.summary.text()
    assert "1 deploy status unknown" in window.summary.text()
    assert _table_text(window, 0, 2) == "Client / Building"
    assert _table_text(window, 0, 7) == "-"
    assert _table_text(window, 0, 8) == "Unknown"
    assert "No data manifest exists yet" in window.detail.toPlainText()
    assert "Deploy: unknown" in window.detail.toPlainText()
    assert window.scrape_button.isEnabled()
    assert not window.commit_button.isEnabled()
    assert "git worktree is clean" in window.commit_button.toolTip()

    window.close()


def test_status_tab_disables_scrape_when_phpp_is_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path, with_phpp=False)
    settings = ManagerSettings(projects_root=tmp_path, github_owner="example", github_repo="manager")
    window = MainWindow(settings, [read_project_status(project, settings)])
    window.table.selectRow(0)
    _app().processEvents()

    assert not window.scrape_button.isEnabled()
    assert "PHPP workbook is missing" in window.scrape_button.toolTip()
    assert "PHPP workbook missing" in window.detail.toPlainText()

    window.close()


def _make_project(tmp_path: Path, *, with_phpp: bool) -> Path:
    project = tmp_path / "Sample Project" / "04_Web"
    phpp = tmp_path / "Sample Project" / "07_PHPP" / "model.xlsx"
    project.mkdir(parents=True)
    phpp.parent.mkdir()
    if with_phpp:
        phpp.write_text("fixture")
    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": "sample",
                "project_title": "Sample Project",
                "client_name": "Client",
                "building_name": "Building",
                "phase": "Design",
                "source_files": {"phpp_path": "../07_PHPP/model.xlsx", "data_dir": "data"},
            },
            sort_keys=False,
        )
    )
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "add", "project.yaml"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=project, check=True, capture_output=True)
    return project


def _app() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _table_text(window: MainWindow, row: int, column: int) -> str:
    item = window.table.item(row, column)
    assert item is not None
    return item.text()
