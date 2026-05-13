"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from bt_web_report_manager.projects import discover_projects
from bt_web_report_manager.settings import load_settings
from bt_web_report_manager.ui.main_window import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    settings = load_settings()
    window = MainWindow(settings=settings, projects=discover_projects(settings))
    window.show()
    return app.exec()
