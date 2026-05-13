"""Main manager window."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QDialog,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from bt_web_report_manager.commands import (
    CommandSpec,
    commit_push_command,
    dev_preview_command,
    doctor,
    open_editor_command,
    reveal_command,
    scrape_command,
)
from bt_web_report_manager.locks import (
    is_current_user_lock,
    lock_requires_confirmation,
    lock_warning_message,
    read_lock,
    refresh_lock,
    release_lock,
    write_lock,
)
from bt_web_report_manager.models import ManagerSettings, ProjectStatus
from bt_web_report_manager.projects import discover_projects
from bt_web_report_manager.settings import save_settings
from bt_web_report_manager.ui.command_runner import ProcessRunner
from bt_web_report_manager.ui.dialogs import DoctorDialog, SettingsDialog
from bt_web_report_manager.ui.update_worker import UpdateWorker, coerce_update_result

LOCK_REFRESH_INTERVAL_MS = 60_000


class MainWindow(QMainWindow):
    def __init__(self, settings: ManagerSettings, projects: Sequence[ProjectStatus]) -> None:
        super().__init__()
        self.settings = settings
        self.projects = list(projects)
        self._owned_lock_paths: set[Path] = set()
        self._update_thread: QThread | None = None
        self._update_worker: UpdateWorker | None = None
        self._lock_refresh_timer = QTimer(self)
        self._lock_refresh_timer.setInterval(LOCK_REFRESH_INTERVAL_MS)
        self._lock_refresh_timer.timeout.connect(self._refresh_owned_locks)
        self.runner = ProcessRunner()
        self.runner.started.connect(self._command_started)
        self.runner.output.connect(self._append_log)
        self.runner.finished.connect(self._command_finished)
        self.setWindowTitle("bt-web-report Manager")
        self.resize(1180, 720)
        self._build_toolbar()
        self._build_content()
        self._render_projects()
        self._lock_refresh_timer.start()
        QTimer.singleShot(250, self.check_updates)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Manager")
        toolbar.setMovable(False)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_projects)
        toolbar.addWidget(refresh)
        settings = QPushButton("Settings")
        settings.clicked.connect(self.open_settings)
        toolbar.addWidget(settings)
        doctor_button = QPushButton("Doctor")
        doctor_button.clicked.connect(self.open_doctor)
        toolbar.addWidget(doctor_button)
        update_button = QPushButton("Check updates")
        update_button.clicked.connect(self.check_updates)
        toolbar.addWidget(update_button)
        toolbar.addSeparator()
        self.root_label = QLabel()
        toolbar.addWidget(self.root_label)
        self.addToolBar(toolbar)

    def _build_content(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_status_tab(), "Status")
        self.setCentralWidget(tabs)

    def _build_status_tab(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.summary = QLabel()
        left_layout.addWidget(self.summary)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Slug", "Client / Building", "Phase", "PHPP", "Data", "Git", "Lock", "Deploy", "Badges"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._render_selected_project)
        left_layout.addWidget(self.table)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.detail_title = QLabel("No project selected")
        self.detail_title.setObjectName("detailTitle")
        right_layout.addWidget(self.detail_title)
        buttons = QHBoxLayout()
        self.scrape_button = QPushButton("Scrape")
        self.scrape_button.clicked.connect(self.run_scrape)
        buttons.addWidget(self.scrape_button)
        self.dev_button = QPushButton("Dev preview")
        self.dev_button.clicked.connect(self.run_dev_preview)
        buttons.addWidget(self.dev_button)
        self.commit_button = QPushButton("Commit & push")
        self.commit_button.clicked.connect(self.run_commit_push)
        self.commit_button.setToolTip("Creates a local commit and pushes the current branch after confirmation.")
        buttons.addWidget(self.commit_button)
        self.reveal_button = QPushButton("Reveal")
        self.reveal_button.clicked.connect(self.run_reveal)
        buttons.addWidget(self.reveal_button)
        self.editor_button = QPushButton("Open editor")
        self.editor_button.clicked.connect(self.run_open_editor)
        buttons.addWidget(self.editor_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.runner.stop)
        buttons.addWidget(self.stop_button)
        self.copy_log_button = QPushButton("Copy log")
        self.copy_log_button.clicked.connect(self.copy_log)
        buttons.addWidget(self.copy_log_button)
        right_layout.addLayout(buttons)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        right_layout.addWidget(self.detail)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Action log")
        right_layout.addWidget(self.log)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([760, 420])
        self._set_action_enabled(False)
        return splitter

    def refresh_projects(self) -> None:
        self._refresh_projects_preserving_selection()

    def _render_projects(self, selected_path: Path | None = None) -> None:
        self.table.setRowCount(len(self.projects))
        dirty = sum(1 for project in self.projects if project.git.dirty_count)
        needs_scrape = sum(1 for project in self.projects if project.needs_scrape)
        deploy_unknown = len(self.projects)
        self.root_label.setText(f"Projects root: {self.settings.projects_root}")
        self.summary.setText(
            f"{len(self.projects)} projects | {dirty} dirty | {needs_scrape} need scrape | "
            f"{deploy_unknown} deploy status unknown"
        )
        for row, project in enumerate(self.projects):
            values = [
                project.metadata.project_title,
                project.metadata.slug,
                _client_building_label(project),
                project.metadata.phase or "-",
                _format_dt(project.phpp_modified_at),
                _format_dt(project.manifest_generated_at),
                _git_label(project),
                _lock_table_label(project),
                "Unknown",
                ", ".join(project.badges),
            ]
            tooltip = "\n".join(_status_explanations(project))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if tooltip:
                    item.setToolTip(tooltip)
                self.table.setItem(row, column, item)
        if self.projects:
            selected_row = 0
            if selected_path is not None:
                for row, project in enumerate(self.projects):
                    if project.project_path == selected_path:
                        selected_row = row
                        break
            self.table.selectRow(selected_row)
            self._render_selected_project()
        else:
            self.detail_title.setText("No projects discovered")
            self.detail.setPlainText(
                "No project.yaml files were found under the configured projects root or extra project paths."
            )
            self._set_action_enabled(False)

    def _refresh_projects_preserving_selection(self, selected_path: Path | None = None) -> None:
        selected = selected_path
        if selected is None:
            project = self._selected_project()
            selected = project.project_path if project is not None else None
        self.projects = discover_projects(self.settings)
        self._render_projects(selected)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings = dialog.settings()
        save_settings(self.settings)
        self.refresh_projects()
        self._append_log("Settings saved and project list refreshed.")

    def open_doctor(self) -> None:
        dialog = DoctorDialog(doctor(self.settings))
        dialog.exec()

    def check_updates(self) -> None:
        if self._update_thread is not None:
            self._append_log("Update check already running.")
            return
        self._append_log("Checking GitHub Releases for manager updates...")
        thread = QThread(self)
        worker = UpdateWorker(self.settings)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._update_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_update_worker)
        self._update_thread = thread
        self._update_worker = worker
        thread.start()

    def run_scrape(self) -> None:
        project = self._selected_project()
        if project is not None and self._prepare_mutating_action(project):
            self._run_command(scrape_command(project, self.settings))

    def run_dev_preview(self) -> None:
        project = self._selected_project()
        if project is not None and self._prepare_mutating_action(project):
            self._run_command(dev_preview_command(project, self.settings))

    def run_reveal(self) -> None:
        project = self._selected_project()
        if project is not None:
            self._run_command(reveal_command(project))

    def run_open_editor(self) -> None:
        project = self._selected_project()
        if project is not None:
            self._run_command(open_editor_command(project, self.settings))

    def copy_log(self) -> None:
        QApplication.clipboard().setText(self.log.toPlainText())
        self._append_log("Action log copied to clipboard.")

    def run_commit_push(self) -> None:
        project = self._selected_project()
        if project is None or not project.git.is_repo or project.git.dirty_count == 0:
            self._append_log("Commit & push requires a dirty git worktree.")
            return
        message, accepted = QInputDialog.getText(
            self,
            "Commit message",
            "Commit message:",
            text=_suggest_commit_message(project),
        )
        if not accepted or not message.strip():
            self._append_log("Commit & push canceled before commit message confirmation.")
            return
        response = QMessageBox.question(
            self,
            "Commit & push",
            (
                f"This will run git add -A, create a commit, and push the current branch for:\n"
                f"{project.project_path}\n\nContinue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            self._append_log("Commit & push canceled before running git.")
            return
        if self._prepare_mutating_action(project):
            self._run_command(commit_push_command(project, self.settings, message.strip()))

    def _run_command(self, spec: CommandSpec) -> None:
        self.runner.start(spec)

    def _render_selected_project(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        project = self.projects[rows[0].row()]
        self._set_action_enabled(True)
        self.detail_title.setText(project.metadata.project_title)
        lines = [
            f"Path: {project.project_path}",
            f"Slug: {project.metadata.slug}",
            f"Client: {project.metadata.client_name or '-'}",
            f"Building: {project.metadata.building_name or '-'}",
            f"URL: {project.metadata.production_url or '-'}",
            f"PHPP: {project.metadata.phpp_path or '-'}",
            f"Data manifest: {project.manifest_path or '-'}",
            f"Git: {_git_label(project)}",
            f"Remote: {project.git.remote or '-'}",
            f"Last commit: {project.git.last_commit or '-'}",
            f"Lock: {_lock_label(project)}",
            f"Badges: {', '.join(project.badges)}",
            "Deploy: unknown (Cloudflare Pages polling is not wired in v1 yet)",
            "",
            "Status:",
            *_status_explanations(project),
            "",
            "Actions:",
            *_action_explanations(project, self.runner.is_running),
        ]
        if project.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in project.warnings)
        self.detail.setPlainText("\n".join(lines))

    def _selected_project(self) -> ProjectStatus | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.projects[rows[0].row()]

    def _set_action_enabled(self, enabled: bool) -> None:
        running = self.runner.is_running
        project = self._selected_project()
        button_states = {
            self.scrape_button: _scrape_disabled_reason(project, running, enabled),
            self.dev_button: _selected_disabled_reason(project, running, enabled),
            self.reveal_button: _selected_disabled_reason(project, running, enabled),
            self.editor_button: _selected_disabled_reason(project, running, enabled),
            self.commit_button: _commit_disabled_reason(project, running, enabled),
        }
        for button, reason in button_states.items():
            button.setEnabled(reason is None)
            button.setToolTip(reason or "")
        self.stop_button.setEnabled(running)
        self.stop_button.setToolTip("" if running else "Disabled: no command is running.")
        self.copy_log_button.setEnabled(bool(self.log.toPlainText()))

    def _command_started(self, line: str) -> None:
        self._append_log(line)
        self._set_action_enabled(self._selected_project() is not None)

    def _append_log(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        for line in text.splitlines() or [""]:
            self.log.append(f"[{timestamp}] {line}")
        if hasattr(self, "copy_log_button"):
            self.copy_log_button.setEnabled(bool(self.log.toPlainText()))

    def _command_finished(self, name: str, exit_code: int, refresh_on_success: bool, canceled: bool) -> None:
        if canceled:
            self._append_log(f"{name} stopped by user.")
        else:
            self._append_log(f"{name} finished with exit code {exit_code}.")
        if not canceled and exit_code == 0 and refresh_on_success:
            self.refresh_projects()
        self._set_action_enabled(self._selected_project() is not None)

    def _update_finished(self, value: object) -> None:
        result = coerce_update_result(value)
        self._append_log(result.message)
        if result.ok and result.release is not None and result.release.is_update:
            QMessageBox.information(
                self,
                "Update available",
                f"{result.release.version} is available.\n\n{result.release.url}",
            )

    def _clear_update_worker(self) -> None:
        self._update_thread = None
        self._update_worker = None

    def _prepare_mutating_action(self, project: ProjectStatus) -> bool:
        lock = read_lock(project.project_path)
        if lock_requires_confirmation(lock):
            assert lock is not None
            response = QMessageBox.warning(
                self,
                "Project lock",
                lock_warning_message(lock),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                self._append_log("Action canceled because the project is locked.")
                return False
        write_lock(project.project_path, project.metadata.slug, self.settings.lock_ttl_hours)
        self._owned_lock_paths.add(project.project_path)
        self._append_log(f"Lock refreshed for {project.metadata.slug}.")
        self._refresh_projects_preserving_selection(project.project_path)
        return True

    def _refresh_owned_locks(self) -> None:
        refreshed_any = False
        for project_path in tuple(self._owned_lock_paths):
            lock = read_lock(project_path)
            if lock is None:
                self._owned_lock_paths.discard(project_path)
                continue
            if lock.malformed or not is_current_user_lock(lock):
                continue
            refresh_lock(project_path, self.settings.lock_ttl_hours)
            refreshed_any = True
        if refreshed_any:
            self._refresh_projects_preserving_selection()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._lock_refresh_timer.stop()
        self.runner.shutdown()
        for project_path in tuple(self._owned_lock_paths):
            lock = read_lock(project_path)
            if lock is not None and not lock.malformed and is_current_user_lock(lock):
                release_lock(project_path)
                self._owned_lock_paths.discard(project_path)
        event.accept()


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def _git_label(project: ProjectStatus) -> str:
    if not project.git.is_repo:
        return "No git"
    branch = project.git.branch or "detached"
    sync: list[str] = []
    if project.git.ahead:
        sync.append(f"{project.git.ahead} ahead")
    if project.git.behind:
        sync.append(f"{project.git.behind} behind")
    sync_text = f" ({', '.join(sync)})" if sync else ""
    if project.git.dirty_count:
        return f"{branch}, {project.git.dirty_count} dirty{sync_text}"
    return f"{branch}, clean{sync_text}"


def _lock_label(project: ProjectStatus) -> str:
    lock = project.lock
    if lock is None:
        return "-"
    if lock.malformed:
        return f"Malformed lock at {lock.path}"
    owner = lock.user or "unknown"
    host = lock.host or "unknown host"
    expiry = _format_dt(lock.expires_at)
    return f"{owner} on {host}, expires {expiry}"


def _lock_table_label(project: ProjectStatus) -> str:
    lock = project.lock
    if lock is None:
        return "-"
    if lock.malformed:
        return "Malformed"
    if lock.user is None:
        return "Unknown owner"
    return lock.user


def _client_building_label(project: ProjectStatus) -> str:
    values = [value for value in (project.metadata.client_name, project.metadata.building_name) if value]
    return " / ".join(values) if values else "-"


def _status_explanations(project: ProjectStatus) -> list[str]:
    lines: list[str] = []
    if project.manifest_path is None:
        lines.append("- No data manifest exists yet; run Scrape after the PHPP path is configured.")
    elif project.needs_scrape:
        lines.append("- PHPP is newer than the data manifest; run Scrape before previewing or publishing.")
    else:
        lines.append("- Data is current against the configured PHPP workbook.")

    if not project.git.is_repo:
        lines.append("- Project folder is not a git worktree; Commit & push is unavailable.")
    elif project.git.dirty_count:
        lines.append(f"- Git has {project.git.dirty_count} uncommitted change(s).")
    else:
        lines.append("- Git worktree is clean.")

    if project.git.ahead:
        lines.append(f"- Current branch is {project.git.ahead} commit(s) ahead of upstream.")
    if project.git.behind:
        lines.append(f"- Current branch is {project.git.behind} commit(s) behind upstream; v1 does not auto-pull.")
    if project.lock is not None:
        lines.append(f"- Lock state: {_lock_label(project)}.")
    if project.warnings:
        lines.append("- Project warnings need review before relying on status badges.")
    return lines


def _action_explanations(project: ProjectStatus, running: bool) -> list[str]:
    states = {
        "Scrape": _scrape_disabled_reason(project, running, True),
        "Dev preview": _selected_disabled_reason(project, running, True),
        "Reveal": _selected_disabled_reason(project, running, True),
        "Open editor": _selected_disabled_reason(project, running, True),
        "Commit & push": _commit_disabled_reason(project, running, True),
    }
    return [
        f"- {name}: {'enabled' if reason is None else reason.removeprefix('Disabled: ')}"
        for name, reason in states.items()
    ]


def _selected_disabled_reason(project: ProjectStatus | None, running: bool, enabled: bool) -> str | None:
    if not enabled or project is None:
        return "Disabled: no project selected."
    if running:
        return "Disabled: another command is running."
    return None


def _scrape_disabled_reason(project: ProjectStatus | None, running: bool, enabled: bool) -> str | None:
    reason = _selected_disabled_reason(project, running, enabled)
    if reason is not None:
        return reason
    assert project is not None
    if project.metadata.phpp_path is None:
        return "Disabled: project.yaml does not define source_files.phpp_path."
    if not project.metadata.phpp_path.exists():
        return "Disabled: configured PHPP workbook is missing."
    return None


def _commit_disabled_reason(project: ProjectStatus | None, running: bool, enabled: bool) -> str | None:
    reason = _selected_disabled_reason(project, running, enabled)
    if reason is not None:
        return reason
    assert project is not None
    if not project.git.is_repo:
        return "Disabled: project folder is not a git worktree."
    if project.git.dirty_count == 0:
        return "Disabled: git worktree is clean."
    return None


def _suggest_commit_message(project: ProjectStatus) -> str:
    if project.needs_scrape:
        return f"Update {project.metadata.slug} report data"
    return f"Update {project.metadata.slug} report"
