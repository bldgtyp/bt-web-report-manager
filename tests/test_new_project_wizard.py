import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.ui.command_runner import ProcessRunner
from bt_web_report_manager.ui.dialogs import NewProjectWizard

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_new_project_wizard_build_page_shows_manual_blocker_when_btwr_new_is_missing(tmp_path: Path) -> None:
    _app()
    local_folder = tmp_path / "Project"
    settings = ManagerSettings(projects_root=tmp_path, btwr_executable="btwr-missing-for-new-project-test")
    runner = ProcessRunner()
    wizard = NewProjectWizard(settings, runner)
    wizard.show()
    _app().processEvents()

    wizard.info_page.project_title.setText("Project")
    wizard.info_page.slug.setText("project")
    wizard.info_page.local_folder.setText(str(local_folder))
    wizard.info_page.target_web_path.setText(str(local_folder / "04_Web"))

    assert wizard.validateCurrentPage()
    wizard.preview_page.initializePage()
    wizard.build_page.initializePage()
    _app().processEvents()

    preview = wizard.preview_page.preview.toPlainText()
    log = wizard.build_page.log.toPlainText()
    assert "Project title: Project" in preview
    assert "Phase 7 dependency: btwr new is not implemented" in log
    assert f"Create target web folder: {local_folder / '04_Web'}" in log
    assert not runner.is_running

    wizard.close()
    runner.shutdown()


def _app() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
