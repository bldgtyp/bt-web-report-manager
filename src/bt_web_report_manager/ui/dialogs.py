"""Small Qt dialogs for settings and setup checks."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from bt_web_report_manager.models import ManagerSettings, ToolStatus


class SettingsDialog(QDialog):
    def __init__(self, settings: ManagerSettings) -> None:
        super().__init__()
        self.setWindowTitle("Settings")
        self.resize(720, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.projects_root = QLineEdit(str(settings.projects_root))
        self.extra_project_paths = QTextEdit()
        self.extra_project_paths.setPlaceholderText("One project path or project-root path per line")
        self.extra_project_paths.setPlainText("\n".join(str(path) for path in settings.extra_project_paths))
        self.btwr_executable = QLineEdit(settings.btwr_executable)
        self.pnpm_executable = QLineEdit(settings.pnpm_executable)
        self.git_executable = QLineEdit(settings.git_executable)
        self.gh_executable = QLineEdit(settings.gh_executable)
        self.editor_command = QLineEdit(settings.editor_command)
        self.github_owner = QLineEdit(settings.github_owner)
        self.github_repo = QLineEdit(settings.github_repo)
        self.lock_ttl_hours = QSpinBox()
        self.lock_ttl_hours.setRange(1, 48)
        self.lock_ttl_hours.setValue(settings.lock_ttl_hours)

        form.addRow("Projects root", self.projects_root)
        form.addRow("Extra project paths", self.extra_project_paths)
        form.addRow("btwr", self.btwr_executable)
        form.addRow("pnpm", self.pnpm_executable)
        form.addRow("git", self.git_executable)
        form.addRow("gh", self.gh_executable)
        form.addRow("Editor", self.editor_command)
        form.addRow("GitHub owner", self.github_owner)
        form.addRow("GitHub repo", self.github_repo)
        form.addRow("Lock TTL hours", self.lock_ttl_hours)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self) -> ManagerSettings:
        extra_paths = tuple(
            Path(line.strip()).expanduser()
            for line in self.extra_project_paths.toPlainText().splitlines()
            if line.strip()
        )
        return ManagerSettings(
            projects_root=Path(self.projects_root.text()).expanduser(),
            extra_project_paths=extra_paths,
            btwr_executable=self.btwr_executable.text().strip() or "btwr",
            pnpm_executable=self.pnpm_executable.text().strip() or "pnpm",
            git_executable=self.git_executable.text().strip() or "git",
            gh_executable=self.gh_executable.text().strip() or "gh",
            editor_command=self.editor_command.text().strip() or "code",
            github_owner=self.github_owner.text().strip() or "bldgtyp",
            github_repo=self.github_repo.text().strip() or "bt-web-report-manager",
            lock_ttl_hours=self.lock_ttl_hours.value(),
        )


class DoctorDialog(QDialog):
    def __init__(self, statuses: list[ToolStatus]) -> None:
        super().__init__()
        self.setWindowTitle("Doctor")
        self.resize(820, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Local setup checks"))
        table = QTableWidget(len(statuses), 5)
        table.setHorizontalHeaderLabels(["Check", "Status", "Executable", "Resolved path", "Message"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, status in enumerate(statuses):
            values = [
                status.name,
                "OK" if status.ok else "Warning",
                status.executable,
                status.path or "-",
                status.message,
            ]
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
