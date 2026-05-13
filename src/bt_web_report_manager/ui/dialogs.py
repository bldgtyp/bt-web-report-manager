"""Small Qt dialogs for settings and setup checks."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from bt_web_report_manager.models import ManagerSettings, ToolStatus
from bt_web_report_manager.new_project import (
    NewProjectPlan,
    bootstrap_command,
    bootstrap_command_available,
    build_new_project_plan,
)
from bt_web_report_manager.ui.command_runner import ProcessRunner


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
        form.addRow("Code editor", self.editor_command)
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


class NewProjectWizard(QWizard):
    def __init__(self, settings: ManagerSettings, runner: ProcessRunner) -> None:
        super().__init__()
        self.settings = settings
        self.runner = runner
        self._plan: NewProjectPlan | None = None
        self.setWindowTitle("New project")
        self.resize(820, 620)
        self.info_page = NewProjectInfoPage(settings)
        self.preview_page = NewProjectPreviewPage(self)
        self.build_page = NewProjectBuildPage(self)
        self.addPage(self.info_page)
        self.addPage(self.preview_page)
        self.addPage(self.build_page)

    def validateCurrentPage(self) -> bool:
        if self.currentPage() is self.info_page:
            try:
                self._plan = self.info_page.plan()
            except ValueError as exc:
                QMessageBox.warning(self, "New project validation", str(exc))
                return False
        return super().validateCurrentPage()

    def plan(self) -> NewProjectPlan | None:
        return self._plan


class NewProjectInfoPage(QWizardPage):
    def __init__(self, settings: ManagerSettings) -> None:
        super().__init__()
        self.settings = settings
        self.setTitle("Project info")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.project_title = QLineEdit()
        self.slug = QLineEdit()
        self.client_name = QLineEdit()
        self.building_name = QLineEdit()
        self.phase = QLineEdit("Design Analysis")
        self.local_folder = QLineEdit(str(settings.projects_root / "Project Name"))
        self.target_web_path = QLineEdit(str(settings.projects_root / "Project Name" / "04_Web"))
        self.phpp_path = QLineEdit()
        self.phpp_path.setPlaceholderText("Optional absolute path to .xlsx or .xlsm")
        self.repo_name = QLineEdit()
        self.production_url = QLineEdit()

        self.slug.textChanged.connect(self._sync_defaults)
        self.local_folder.textChanged.connect(self._sync_target_path)

        form.addRow("Project title", self.project_title)
        form.addRow("Slug", self.slug)
        form.addRow("Client", self.client_name)
        form.addRow("Building", self.building_name)
        form.addRow("Phase", self.phase)
        form.addRow("Local folder", self.local_folder)
        form.addRow("Target 04_Web path", self.target_web_path)
        form.addRow("PHPP workbook", self.phpp_path)
        form.addRow("Repo name", self.repo_name)
        form.addRow("Production URL", self.production_url)
        layout.addLayout(form)

    def plan(self) -> NewProjectPlan:
        phpp_text = self.phpp_path.text().strip()
        return build_new_project_plan(
            project_title=self.project_title.text(),
            slug=self.slug.text(),
            client_name=self.client_name.text(),
            building_name=self.building_name.text(),
            phase=self.phase.text(),
            local_folder=Path(self.local_folder.text()),
            target_web_path=Path(self.target_web_path.text()),
            phpp_path=Path(phpp_text) if phpp_text else None,
            repo_name=self.repo_name.text(),
            production_url=self.production_url.text(),
        )

    def _sync_defaults(self, value: str) -> None:
        if not self.repo_name.text().strip() or self.repo_name.text().startswith("bt-proj-"):
            self.repo_name.setText(f"bt-proj-{value}" if value else "")
        if not self.production_url.text().strip() or self.production_url.text().endswith(".bldgtyp.com"):
            self.production_url.setText(f"https://{value}.bldgtyp.com" if value else "")

    def _sync_target_path(self, value: str) -> None:
        if self.target_web_path.text().strip().endswith("/04_Web"):
            self.target_web_path.setText(str(Path(value).expanduser() / "04_Web"))


class NewProjectPreviewPage(QWizardPage):
    def __init__(self, wizard: NewProjectWizard) -> None:
        super().__init__()
        self._wizard = wizard
        self.setTitle("Confirmation preview")
        layout = QVBoxLayout(self)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview)

    def initializePage(self) -> None:
        plan = self._wizard.plan()
        if plan is None:
            self.preview.setPlainText("No valid project creation plan is available.")
            return
        self.preview.setPlainText("\n".join(plan.summary_lines()))


class NewProjectBuildPage(QWizardPage):
    def __init__(self, wizard: NewProjectWizard) -> None:
        super().__init__()
        self._wizard = wizard
        self.setTitle("Build / log")
        layout = QVBoxLayout(self)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def initializePage(self) -> None:
        plan = self._wizard.plan()
        if plan is None:
            self.log.setPlainText("No valid project creation plan is available.")
            return
        lines = ["Validated project creation plan:", "", *plan.summary_lines(), ""]
        if bootstrap_command_available(self._wizard.settings):
            spec = bootstrap_command(plan, self._wizard.settings)
            lines.extend(["Running bootstrap command:", "$ " + " ".join(spec.args)])
            self.log.setPlainText("\n".join(lines))
            self._wizard.runner.start(spec)
        else:
            lines.extend(plan.manual_checklist())
            self.log.setPlainText("\n".join(lines))
