import os
from pathlib import Path

import yaml
from PySide6.QtWidgets import QApplication, QMessageBox
from pytest import MonkeyPatch

from bt_web_report_manager.locks import current_host, current_user, read_lock
from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.projects import read_project_status
from bt_web_report_manager.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_mutating_action_cancel_preserves_other_user_lock(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    project = _make_project(tmp_path)
    _write_other_user_lock(project)
    window = _make_window(project, tmp_path)
    monkeypatch.setattr(QMessageBox, "warning", _deny_lock_override)

    allowed = window._prepare_mutating_action(window.projects[0])

    lock = read_lock(project)
    assert not allowed
    assert lock is not None
    assert lock.user == "john"
    assert lock.host == "Johns-Mac.local"
    window.close()


def test_mutating_action_override_replaces_other_user_lock(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    project = _make_project(tmp_path)
    _write_other_user_lock(project)
    window = _make_window(project, tmp_path)
    monkeypatch.setattr(QMessageBox, "warning", _allow_lock_override)

    allowed = window._prepare_mutating_action(window.projects[0])

    lock = read_lock(project)
    assert allowed
    assert lock is not None
    assert lock.user == current_user()
    assert lock.host == current_host()
    window.close()


def _make_window(project: Path, tmp_path: Path) -> MainWindow:
    app = QApplication.instance() or QApplication([])
    settings = ManagerSettings(projects_root=tmp_path, github_owner="example", github_repo="manager")
    window = MainWindow(settings, [read_project_status(project, settings)])
    window.table.selectRow(0)
    app.processEvents()
    return window


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "Sample Project" / "04_Web"
    project.mkdir(parents=True)
    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": "sample",
                "project_title": "Sample Project",
                "source_files": {"data_dir": "data"},
            },
            sort_keys=False,
        )
    )
    return project


def _write_other_user_lock(project: Path) -> None:
    lock_path = project / ".bldgtyp" / "lock.yaml"
    lock_path.parent.mkdir()
    lock_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "user": "john",
                "host": "Johns-Mac.local",
                "project_slug": "sample",
                "opened_at": "2026-05-13T12:00:00+00:00",
                "updated_at": "2026-05-13T12:00:00+00:00",
                "expires_at": "2099-05-13T16:00:00+00:00",
            },
            sort_keys=False,
        )
    )


def _deny_lock_override(*args: object) -> QMessageBox.StandardButton:
    return QMessageBox.StandardButton.No


def _allow_lock_override(*args: object) -> QMessageBox.StandardButton:
    return QMessageBox.StandardButton.Yes
