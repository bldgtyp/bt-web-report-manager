"""Background update check worker."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from bt_web_report_manager import __version__
from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.updates import UpdateCheckResult, check_for_updates


class UpdateWorker(QObject):
    finished = Signal(object)

    def __init__(self, settings: ManagerSettings) -> None:
        super().__init__()
        self.settings = settings

    @Slot()
    def run(self) -> None:
        result = check_for_updates(
            self.settings.github_owner,
            self.settings.github_repo,
            __version__,
            timeout=3,
        )
        self.finished.emit(result)


def coerce_update_result(value: object) -> UpdateCheckResult:
    if isinstance(value, UpdateCheckResult):
        return value
    return UpdateCheckResult(False, f"Unexpected update-check result: {value!r}")
