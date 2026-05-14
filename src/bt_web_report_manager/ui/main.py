"""Main manager page.

Renders the toolbar, project table, detail pane, action cluster, and log.
Owns the ``ProcessRunner``, lock-refresh timer, and shutdown hook for
releasing locks. All UI state lives in ``ManagerState`` (in ``state.py``).
"""

from __future__ import annotations

import asyncio
import webbrowser
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from nicegui import app, ui

import pyperclip  # type: ignore[import-untyped]

from bt_web_report_manager import __version__
from bt_web_report_manager.commands import (
    CommandSpec,
    commit_push_command,
    dev_preview_command,
    open_code_editor_command,
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
from bt_web_report_manager.models import ProjectStatus
from bt_web_report_manager.projects import discover_projects
from bt_web_report_manager.settings import save_settings
from bt_web_report_manager.ui.command_feedback import (
    ScrapeRunFeedback,
    scrape_error_summary,
    scrape_success_summary,
)
from bt_web_report_manager.ui.dialogs import (
    confirm_dialog,
    open_doctor_dialog,
    open_settings_dialog,
    prompt_dialog,
)
from bt_web_report_manager.ui.helpers import (
    action_card_states,
    badges_html,
    commit_disabled_reason,
    format_dt,
    git_label,
    lock_label,
    open_editor_disabled_reason,
    ProjectMetric,
    project_file_locations,
    project_metrics,
    project_row,
    scrape_disabled_reason,
    selected_disabled_reason,
    status_explanations,
    suggest_commit_message,
)
from bt_web_report_manager.ui.new_project import open_new_project_wizard
from bt_web_report_manager.ui.preview import local_preview_url_from_log_line
from bt_web_report_manager.ui.runner import ProcessRunner
from bt_web_report_manager.ui.state import ManagerState
from bt_web_report_manager.ui.theme import apply_theme
from bt_web_report_manager.ui.updates import run_update_check
from bt_web_report_manager.trace import trace_event, trace_exception

LOCK_REFRESH_INTERVAL_SECONDS = 60.0

ACTIVE_TOOLTIPS: dict[str, str] = {
    "scrape": "Run btwr scrape against the configured PHPP workbook. Writes a Dropbox lock.",
    "dev": "Start pnpm dev for live local preview at http://localhost:4321.",
    "editor": "Start the TinaCMS authoring server (pnpm dev:editor) to edit project content.",
    "code_editor": "Open this project in the configured code editor (VS Code / Cursor / etc).",
    "commit": "git add -A, commit with a message, and push the current branch.",
    "reveal": "Open the project folder in Finder.",
}


def build_page(state: ManagerState) -> None:
    """Render the manager UI bound to ``state``. Call inside ``@ui.page``."""
    trace_event(
        "ui.main.build_page", settings=state.settings, project_count=len(state.projects), selected=state.selected_slug
    )
    apply_theme()

    # Mutable refs filled in during construction below
    log_ref: dict[str, Any] = {}
    btns: dict[str, Any] = {}
    btn_tips: dict[str, Any] = {}
    led_ref: dict[str, Any] = {}
    log_lines: list[str] = []
    current_screen = {"name": "index"}
    scrape_feedback: dict[str, Any] = {"run": None, "dialog": None, "title": None, "message": None, "spinner": None}
    preview_browser = {"armed": False, "opened": False}

    def log_message(text: str) -> None:
        trace_event("ui.main.log_message", text=text)
        ts = datetime.now().strftime("%H:%M:%S")
        log_widget = log_ref.get("widget")
        for line in text.splitlines() or [""]:
            stamped = f"[{ts}] {line}"
            log_lines.append(stamped)
            if log_widget is not None:
                log_widget.push(stamped)
            else:
                print(stamped)

    def on_runner_log(line: str) -> None:
        trace_event("ui.main.runner_log", line=line)
        active_scrape = scrape_feedback.get("run")
        if isinstance(active_scrape, ScrapeRunFeedback):
            active_scrape.output_lines.append(line)
        log_message(line)
        maybe_open_dev_preview(line)

    def on_runner_done(name: str, exit_code: int, refresh_on_success: bool, canceled: bool) -> None:
        trace_event(
            "ui.main.runner_done",
            name=name,
            exit_code=exit_code,
            refresh_on_success=refresh_on_success,
            canceled=canceled,
        )
        if canceled:
            log_message(f"{name} stopped by user.")
        else:
            log_message(f"{name} finished with exit code {exit_code}.")
        if name == "Dev preview":
            preview_browser["armed"] = False
            preview_browser["opened"] = False
        if name == "Scrape":
            ui.timer(0, lambda: _finish_scrape_feedback(exit_code=exit_code, canceled=canceled), once=True)
        # Apply idle state immediately. The timer below still owns any async
        # refresh work, but buttons should not remain disabled if that callback
        # is delayed by the browser/client event cycle.
        running_led_set(False)
        refresh_action_state()
        # Schedule the UI update via a timer so the slot context is preserved
        ui.timer(0, lambda: _post_command_refresh(refresh_on_success and exit_code == 0 and not canceled), once=True)

    def maybe_open_dev_preview(line: str) -> None:
        if not preview_browser["armed"] or preview_browser["opened"]:
            return
        url = local_preview_url_from_log_line(line)
        if url is None:
            return
        preview_browser["opened"] = True
        trace_event("ui.action.dev_preview.open_browser", url=url)
        try:
            opened = webbrowser.open(url, new=1)
        except Exception as exc:
            trace_exception("ui.action.dev_preview.open_browser_failed", exc, url=url)
            log_message(f"Dev preview is ready, but the browser did not open: {url}")
            return
        if opened:
            log_message(f"Opened dev preview in browser: {url}")
        else:
            log_message(f"Dev preview is ready: {url}")

    def _post_command_refresh(do_refresh: bool) -> None:
        trace_event("ui.main.post_command_refresh", do_refresh=do_refresh)
        running_led_set(False)
        if do_refresh:
            ui.timer(0, refresh_projects, once=True)
        else:
            refresh_action_state()

    def _begin_scrape_feedback(project: ProjectStatus, spec: CommandSpec) -> None:
        trace_event("ui.scrape_feedback.begin", project=project.project_path, slug=project.metadata.slug)
        phpp_filename = project.metadata.phpp_path.name if project.metadata.phpp_path is not None else "configured PHPP"
        progress_dialog = ui.dialog().props("persistent")
        with progress_dialog, ui.card().classes("min-w-[460px] max-w-[620px]"):
            title = ui.label(f"Scraping PHPP {phpp_filename}").classes("dialog-title")
            ui.label(project.metadata.project_title).classes("dialog-subtitle")
            with ui.row().classes("w-full items-center gap-3 mt-2"):
                spinner = ui.spinner(size="24px")
                message = ui.label("Reading the PHPP workbook and writing report data files.").classes(
                    "scrape-dialog-message"
                )
            ui.label(f"Output folder: {project.metadata.data_dir}").style(
                "font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);"
            )
            with ui.row().classes("w-full justify-end mt-4"):
                close_button = (
                    ui.button("Close", on_click=progress_dialog.close, color=None)
                    .props("flat unelevated no-caps")
                    .classes("action-btn")
                )
                close_button.set_enabled(False)
        scrape_feedback["run"] = ScrapeRunFeedback(
            project_title=project.metadata.project_title,
            project_slug=project.metadata.slug,
            project_path=project.project_path,
            phpp_path=project.metadata.phpp_path,
            data_dir=project.metadata.data_dir,
            args=spec.args,
            cwd=spec.cwd,
        )
        scrape_feedback["dialog"] = progress_dialog
        scrape_feedback["title"] = title
        scrape_feedback["message"] = message
        scrape_feedback["spinner"] = spinner
        scrape_feedback["close_button"] = close_button
        screen_container.classes(add="is-frozen")
        progress_dialog.open()

    async def _finish_scrape_feedback(exit_code: int, canceled: bool) -> None:
        active_scrape = scrape_feedback.get("run")
        title = scrape_feedback.get("title")
        message = scrape_feedback.get("message")
        spinner = scrape_feedback.get("spinner")
        close_button = scrape_feedback.get("close_button")
        scrape_feedback["run"] = None
        screen_container.classes(remove="is-frozen")
        if not isinstance(active_scrape, ScrapeRunFeedback):
            trace_event("ui.scrape_feedback.finish.no_active_run", exit_code=exit_code, canceled=canceled)
            return

        if exit_code == 0 and not canceled:
            trace_event("ui.scrape_feedback.success", project=active_scrape.project_path)
            if title is not None:
                title.text = "Scrape PHPP complete"
            if message is not None:
                message.text = scrape_success_summary(active_scrape)
            if spinner is not None:
                spinner.set_visibility(False)
            if close_button is not None:
                close_button.set_enabled(True)
            return

        trace_event(
            "ui.scrape_feedback.error",
            project=active_scrape.project_path,
            exit_code=exit_code,
            canceled=canceled,
        )
        if title is not None:
            title.text = "Scrape PHPP error"
        if message is not None:
            message.text = scrape_error_summary(active_scrape, exit_code=exit_code, canceled=canceled)
        if spinner is not None:
            spinner.set_visibility(False)
        if close_button is not None:
            close_button.set_enabled(True)

    runner = ProcessRunner(on_log=on_runner_log, on_done=on_runner_done)

    # ---- Header / toolbar -------------------------------------------------
    with ui.element("div").classes("app-header"):
        with ui.element("div").classes("brand"):
            ui.html('<span class="brand-mark">bt</span>')
            ui.label("bt-web-report Manager")
            ui.label(f"v{__version__}").style(
                "color: #a8a29e; font-family: var(--font-mono); font-size: 11px; margin-left: 6px;"
            )

        def _toolbar_click(label: str, handler: Any) -> Any:
            trace_event("ui.toolbar.clicked", label=label)
            return handler()

        def _tool_button(label: str, icon: str, handler: Any, modifier: str, tip: str) -> None:
            with (
                ui.button(
                    label,
                    icon=icon,
                    color=None,
                    on_click=lambda label=label, handler=handler: _toolbar_click(label, handler),
                )
                .props("flat unelevated no-caps")
                .classes(f"tool-btn {modifier}".strip())
            ):
                ui.tooltip(tip)

        _tool_button(
            "New project",
            "add",
            lambda: on_new_project(),
            "is-primary",
            "Create a new Passive House project (Cmd+N).",
        )
        _tool_button(
            "Refresh",
            "refresh",
            lambda: refresh_projects(),
            "",
            "Re-scan projects root and any extra paths (Cmd+R).",
        )
        _tool_button(
            "Settings",
            "tune",
            lambda: on_settings(),
            "",
            "Paths, tools, GitHub release source, lock TTL (Cmd+,).",
        )
        _tool_button(
            "System Check",
            "medical_services",
            lambda: on_doctor(),
            "",
            "Read-only check of btwr, pnpm, git, gh, editor, and settings folder.",
        )
        _tool_button(
            "Check updates",
            "cloud_download",
            lambda: on_check_updates(),
            "",
            "Poll GitHub Releases for a newer manager build.",
        )

        root_tag = ui.html("").classes("root-tag")

    screen_container = ui.element("div").classes("screen-root")

    # ---- Helpers ----------------------------------------------------------
    def running_led_set(is_running: bool) -> None:
        led = led_ref.get("widget")
        if led is not None:
            led.classes(replace="led" if is_running else "led idle")

    def render_page() -> None:
        root_tag.content = f'<span style="color:#a8a29e;">root</span> &nbsp; {state.settings.projects_root}'
        btns.clear()
        btn_tips.clear()
        led_ref.clear()
        log_ref.clear()
        screen_container.clear()
        if current_screen["name"] == "workspace" and state.selected_project() is not None:
            render_workspace()
        else:
            current_screen["name"] = "index"
            render_index()
        refresh_action_state()

    def render_index() -> None:
        with screen_container:
            with ui.element("div").classes("index-screen"):
                with ui.element("div").classes("index-hero"):
                    with ui.element("div"):
                        ui.label("Projects").classes("index-title")
                        ui.label("Portfolio scan, project setup, and entry point into one project workspace.").classes(
                            "index-subtitle"
                        )
                    ui.label(f"Last scan {datetime.now().strftime('%H:%M:%S')}").classes("index-meta")

                with ui.element("div").classes("summary-bar summary-bar-large"):
                    metrics = [*project_metrics(state.projects), ProjectMetric("Deploy unknown", len(state.projects))]
                    for i, metric in enumerate(metrics):
                        if i > 0:
                            ui.element("div").classes("divider")
                        with ui.element("div").classes("metric"):
                            ui.html(f'<span class="num">{metric.value}</span><span>{metric.label}</span>')

        if not state.projects:
            with screen_container:
                with ui.element("div").classes("empty-state"):
                    ui.icon("folder_off").style("font-size: 30px;")
                    ui.label("No projects discovered").classes("empty-title")
                    ui.label(
                        "No project.yaml files were found under the configured projects root or extra "
                        "project paths. Open Settings to adjust the roots, then Refresh."
                    ).classes("empty-body")
            return

        with screen_container:
            ui.label("Click a project to open its workspace.").classes("section-note")
            with ui.element("div").classes("project-list"):
                with ui.element("div").classes("project-list-header"):
                    for label in ("Name", "Slug", "Client / Building", "Phase", "PHPP", "Data", "Git", "Status", ""):
                        ui.label(label)
                for project in state.projects:
                    row = project_row(project)
                    with ui.element("div").classes("project-list-row"):
                        _project_cell(row["name"], "project-cell project-name", project.metadata.slug)
                        _project_cell(row["slug"], "project-cell col-mono", project.metadata.slug)
                        _project_cell(row["client_building"], "project-cell", project.metadata.slug)
                        _project_cell(row["phase"], "project-cell", project.metadata.slug)
                        _project_cell(row["phpp"], "project-cell col-mono", project.metadata.slug)
                        _project_cell(row["data"], "project-cell col-mono", project.metadata.slug)
                        _project_cell(row["git"], "project-cell", project.metadata.slug)
                        ui.html(row["badges_html"]).classes("project-cell project-status-cell").on(
                            "click", lambda _e, slug=project.metadata.slug: open_workspace(slug)
                        )
                        ui.button(
                            icon="delete",
                            color=None,
                            on_click=lambda _e, selected=project: ui.timer(
                                0, lambda: delete_project(selected), once=True
                            ),
                        ).props("flat dense round").classes("icon-tool project-delete-button")

    def open_workspace(slug: str) -> None:
        state.selected_slug = slug
        current_screen["name"] = "workspace"
        render_page()

    def _project_cell(text: str, classes: str, slug: str) -> None:
        ui.label(text).classes(classes).on("click", lambda _e, selected_slug=slug: open_workspace(selected_slug))

    def back_to_index() -> None:
        current_screen["name"] = "index"
        render_page()

    def render_workspace() -> None:
        project = state.selected_project()
        if project is None:
            return
        with screen_container:
            with ui.element("div").classes("workspace-screen"):
                with ui.element("div").classes("breadcrumb-strip"):
                    ui.button("All projects", icon="chevron_left", color=None, on_click=back_to_index).props(
                        "flat unelevated no-caps"
                    ).classes("breadcrumb-button")
                    ui.label(f"{len(state.projects)} projects").classes("breadcrumb-meta")
                    ui.label("/").classes("breadcrumb-meta")
                    ui.label(project.metadata.project_title).classes("breadcrumb-current")

                with ui.element("div").classes("project-identity"):
                    with ui.element("div").classes("project-title-row"):
                        ui.label(project.metadata.project_title).classes("workspace-title")
                        ui.html(badges_html(project.badges)).classes("workspace-badges")
                    with ui.element("div").classes("project-meta-row"):
                        _meta_pill(project.metadata.slug)
                        _meta_text("Client", project.metadata.client_name)
                        _meta_text("Building", project.metadata.building_name)
                        _meta_text("Phase", project.metadata.phase)
                    with ui.element("div").classes("project-link-row"):
                        if project.metadata.production_url:
                            ui.icon("language").classes("inline-icon")
                            ui.link(
                                project.metadata.production_url, project.metadata.production_url, new_tab=True
                            ).classes("project-url")
                        ui.label(f"PHPP modified {format_dt(project.phpp_modified_at)}").classes("project-timestamp")
                        ui.label(f"Data refreshed {format_dt(project.manifest_generated_at)}").classes(
                            "project-timestamp"
                        )

                with ui.element("div").classes("workspace-action-grid"):
                    _action_group(
                        "Run",
                        "run",
                        [
                            ("scrape", "play_arrow", run_scrape, "is-warning"),
                            ("dev", "flare", run_dev_preview, ""),
                        ],
                    )
                    _action_group(
                        "Author",
                        "author",
                        [
                            ("editor", "edit_square", run_open_editor, ""),
                            ("code_editor", "code", run_open_code_editor, ""),
                        ],
                    )
                    _action_group(
                        "Publish",
                        "publish",
                        [
                            ("commit", "upload", run_commit_push, "is-primary"),
                            ("reveal", "folder_open", run_reveal, ""),
                        ],
                    )
                    _process_group()

                with ui.element("div").classes("workspace-lower-grid"):
                    render_files_locations(project)
                    render_action_log(project)
                    render_status_notes(project)

    def _kv(key: str, value: str) -> None:
        ui.html(f'<div class="k">{key}</div><div class="v">{value}</div>')

    def _meta_pill(value: str) -> None:
        ui.label(value).classes("meta-pill")

    def _meta_text(label: str, value: str | None) -> None:
        if value:
            ui.html(f'<span class="meta-label">{label}</span><span class="meta-value">{value}</span>')

    def _action_group(label: str, marker: str, items: list[tuple[str, str, Any, str]]) -> None:
        states = action_card_states(state.selected_project(), runner.is_running, state.selected_project() is not None)
        with ui.element("div").classes("action-card-group"):
            ui.label(label).classes(f"action-group-label marker-{marker}")
            for key, icon, handler, modifier in items:
                card_state = states[key]
                _action_button(key, card_state.label, card_state.detail, icon, handler, modifier)

    def _process_group() -> None:
        with ui.element("div").classes("action-card-group"):
            ui.label("Process").classes("action-group-label marker-process")
            _action_button("stop", "Stop", "Stop running process", "stop_circle", on_stop, "is-danger")
            _action_button("copy_log", "Copy log", "Copy current action log", "content_copy", on_copy_log, "")

    def _action_button(key: str, label: str, detail: str, icon: str, handler: Any, modifier: str = "") -> None:
        def _click() -> Any:
            project = state.selected_project()
            trace_event(
                "ui.action.clicked",
                key=key,
                label=label,
                selected_project=project.project_path if project is not None else None,
                selected_slug=project.metadata.slug if project is not None else None,
                running=runner.is_running,
            )
            return handler()

        with (
            ui.button(color=None, on_click=_click)
            .props("flat unelevated no-caps")
            .classes(f"action-btn action-card-button {modifier}".strip()) as button
        ):
            with ui.element("div").classes("action-button-inner"):
                ui.icon(icon).classes("action-button-icon")
                with ui.element("div").classes("action-button-text"):
                    ui.label(label).classes("action-button-label")
                    ui.label(detail).classes("action-button-detail")
            btn_tips[key] = ui.tooltip(ACTIVE_TOOLTIPS.get(key, detail))
        btns[key] = button

    def render_files_locations(project: ProjectStatus) -> None:
        def _copy_project_paths() -> None:
            trace_event("ui.files.copy_paths.clicked", project=project.project_path)
            copy_project_paths(project)

        with ui.element("div").classes("info-panel files-panel"):
            with ui.element("div").classes("panel-header"):
                ui.label("Files & locations").classes("panel-title")
                ui.button(
                    "Copy paths",
                    icon="content_copy",
                    color=None,
                    on_click=_copy_project_paths,
                ).props(
                    "flat dense unelevated no-caps"
                ).classes("panel-tool")
            for location in project_file_locations(project):

                def _copy_location_value(value: str = location.value, kind: str = location.kind) -> None:
                    trace_event("ui.files.copy_value.clicked", kind=kind, value=value)
                    copy_text(value)

                with ui.element("div").classes("file-row"):
                    ui.label(location.kind).classes(f"file-kind file-kind-{location.kind.lower()}")
                    with ui.element("div").classes("file-main"):
                        ui.label(location.label).classes("file-label")
                        ui.label(location.value).classes("file-value")
                    ui.button(
                        icon="content_copy",
                        color=None,
                        on_click=_copy_location_value,
                    ).props(
                        "flat dense round"
                    ).classes("icon-tool")

    def render_action_log(project: ProjectStatus) -> None:
        with ui.element("div").classes("log-shell workspace-log"):
            with ui.element("div").classes("log-header"):
                led = ui.element("div").classes("led" if runner.is_running else "led idle")
                led_ref["widget"] = led
                ui.label("Action log").style("flex: 1;")
                ui.label(f"scoped · {project.metadata.slug}").classes("log-scope")
            log_widget = ui.log(max_lines=4000).classes("nicegui-log").style("flex: 1; min-height: 210px;")
            log_ref["widget"] = log_widget
            for line in log_lines:
                log_widget.push(line)

    def render_status_notes(project: ProjectStatus) -> None:
        with ui.element("div").classes("info-panel status-panel"):
            ui.label("State").classes("panel-title")
            with ui.element("div").classes("kv-grid"):
                _kv("Git", git_label(project))
                _kv("Remote", project.git.remote or "-")
                _kv("Last commit", project.git.last_commit or "-")
                _kv("Lock", lock_label(project))
                _kv("Deploy", "unknown (Cloudflare polling not wired in v1)")
            ui.label("Status").classes("section-label").style("margin-top: 12px;")
            for line in status_explanations(project):
                ui.label(line).style("font-size: 12.5px; color: var(--text-2); line-height: 1.55;")
            if project.warnings:
                ui.label("Warnings").classes("section-label").style("margin-top: 12px;")
                for warning in project.warnings:
                    ui.label(f"- {warning}").style("font-size: 12.5px; color: var(--danger); line-height: 1.55;")

    def copy_text(text: str) -> None:
        try:
            pyperclip.copy(text)
            log_message("Copied to clipboard.")
        except pyperclip.PyperclipException as exc:
            log_message(f"Clipboard unavailable: {exc}")
            ui.notify("Clipboard unavailable on this machine.", type="warning")

    def copy_project_paths(project: ProjectStatus) -> None:
        copy_text("\n".join(location.value for location in project_file_locations(project)))

    def refresh_action_state() -> None:
        project = state.selected_project()
        running = runner.is_running
        enabled = project is not None

        reasons = {
            "scrape": scrape_disabled_reason(project, running, enabled),
            "dev": selected_disabled_reason(project, running, enabled),
            "editor": open_editor_disabled_reason(project, running, enabled),
            "code_editor": selected_disabled_reason(project, running, enabled),
            "commit": commit_disabled_reason(project, running, enabled),
            "reveal": selected_disabled_reason(project, running, enabled),
        }
        for key, reason in reasons.items():
            btn = btns.get(key)
            tip = btn_tips.get(key)
            if btn is None or tip is None:
                continue
            disabled = reason is not None
            btn.set_enabled(not disabled)
            tip.text = reason if disabled else ACTIVE_TOOLTIPS[key]

        stop_btn = btns.get("stop")
        stop_tip = btn_tips.get("stop")
        if stop_btn is not None and stop_tip is not None:
            stop_btn.set_enabled(running)
            stop_tip.text = "Stop the running command. SIGKILL after 2 s." if running else "No command is running."

    # ---- Actions ----------------------------------------------------------
    async def refresh_projects(preserve_path: Path | None = None) -> None:
        trace_event("ui.projects.refresh.start", preserve_path=preserve_path, settings=state.settings)
        selected_path = preserve_path
        if selected_path is None:
            current = state.selected_project()
            if current is not None:
                selected_path = current.project_path

        state.projects = await asyncio.to_thread(discover_projects, state.settings)
        state.select_project_by_path(selected_path)
        trace_event(
            "ui.projects.refresh.done",
            project_count=len(state.projects),
            selected_path=selected_path,
            selected_slug=state.selected_slug,
            projects=[str(project.project_path) for project in state.projects],
        )
        render_page()

    async def prepare_mutating_action(project: ProjectStatus) -> bool:
        trace_event("ui.mutating_action.prepare.start", project=project.project_path, slug=project.metadata.slug)
        lock = read_lock(project.project_path)
        if lock_requires_confirmation(lock):
            assert lock is not None
            trace_event("ui.mutating_action.lock_confirmation.required", project=project.project_path, lock=lock)
            ok = await confirm_dialog(
                title="Project lock",
                message=lock_warning_message(lock),
                confirm_label="Continue and overwrite",
                danger=True,
            )
            if not ok:
                trace_event("ui.mutating_action.lock_confirmation.cancelled", project=project.project_path)
                log_message("Action canceled because the project is locked.")
                return False
        write_lock(project.project_path, project.metadata.slug, state.settings.lock_ttl_hours)
        state.owned_lock_paths.add(project.project_path)
        trace_event(
            "ui.mutating_action.lock_written", project=project.project_path, ttl_hours=state.settings.lock_ttl_hours
        )
        log_message(f"Lock refreshed for {project.metadata.slug}.")
        await refresh_projects(project.project_path)
        return True

    async def _start_command(spec: CommandSpec) -> bool:
        trace_event("ui.command.start_requested", spec=spec)
        running_led_set(True)
        refresh_action_state()
        started = await runner.start(spec)
        if not started:
            running_led_set(False)
        else:
            running_led_set(True)
        refresh_action_state()
        return started

    async def run_scrape() -> None:
        project = state.selected_project()
        if project is None:
            trace_event("ui.action.scrape.no_project")
            return
        if await prepare_mutating_action(project):
            spec = scrape_command(project, state.settings)
            _begin_scrape_feedback(project, spec)
            started = await _start_command(spec)
            if not started and isinstance(scrape_feedback.get("run"), ScrapeRunFeedback):
                await _finish_scrape_feedback(exit_code=-1, canceled=False)

    async def run_dev_preview() -> None:
        project = state.selected_project()
        if project is None:
            trace_event("ui.action.dev_preview.no_project")
            return
        if await prepare_mutating_action(project):
            preview_browser["armed"] = True
            preview_browser["opened"] = False
            started = await _start_command(dev_preview_command(project, state.settings))
            if not started:
                preview_browser["armed"] = False
                preview_browser["opened"] = False

    async def run_open_editor() -> None:
        project = state.selected_project()
        if project is None:
            trace_event("ui.action.open_editor.no_project")
            return
        if await prepare_mutating_action(project):
            await _start_command(open_editor_command(project, state.settings))

    async def run_open_code_editor() -> None:
        project = state.selected_project()
        if project is not None:
            await _start_command(open_code_editor_command(project, state.settings))
        else:
            trace_event("ui.action.open_code_editor.no_project")

    async def run_reveal() -> None:
        project = state.selected_project()
        if project is not None:
            await _start_command(reveal_command(project))
        else:
            trace_event("ui.action.reveal.no_project")

    async def run_commit_push() -> None:
        project = state.selected_project()
        if project is None or not project.git.is_repo or project.git.dirty_count == 0:
            trace_event(
                "ui.action.commit_push.blocked",
                project=project.project_path if project is not None else None,
                is_repo=project.git.is_repo if project is not None else None,
                dirty_count=project.git.dirty_count if project is not None else None,
            )
            log_message("Commit & push requires a dirty git worktree.")
            return
        message = await prompt_dialog(
            title="Commit & push",
            label="Commit message",
            default=suggest_commit_message(project),
            confirm_label="Next",
        )
        if not message:
            trace_event("ui.action.commit_push.message_cancelled", project=project.project_path)
            log_message("Commit & push canceled before commit message confirmation.")
            return
        ok = await confirm_dialog(
            title="Confirm commit & push",
            message=(
                f"Run git add -A, commit with the message below, and push the current branch?\n\n"
                f"path: {project.project_path}\n"
                f'message: "{message}"'
            ),
            confirm_label="Commit & push",
        )
        if not ok:
            trace_event("ui.action.commit_push.confirm_cancelled", project=project.project_path, message=message)
            log_message("Commit & push canceled before running git.")
            return
        if await prepare_mutating_action(project):
            trace_event("ui.action.commit_push.confirmed", project=project.project_path, message=message)
            await _start_command(commit_push_command(project, state.settings, message))

    def on_stop() -> None:
        trace_event("ui.action.stop.clicked")
        runner.stop()

    def on_copy_log() -> None:
        text = "\n".join(log_lines)
        trace_event("ui.action.copy_log.clicked", line_count=len(log_lines))
        try:
            pyperclip.copy(text)
            log_message("Action log copied to clipboard.")
        except pyperclip.PyperclipException as exc:
            trace_event("ui.action.copy_log.failed", error=str(exc))
            log_message(f"Clipboard unavailable: {exc}")
            ui.notify("Clipboard unavailable on this machine.", type="warning")

    async def on_settings() -> None:
        trace_event("ui.toolbar.settings.open")

        async def _after_save() -> None:
            trace_event("ui.toolbar.settings.after_save")
            log_message("Settings saved and project list refreshed.")
            await refresh_projects()

        await open_settings_dialog(state, on_save=_after_save)

    async def on_doctor() -> None:
        trace_event("ui.toolbar.doctor.open")
        await open_doctor_dialog(state)

    async def on_new_project() -> None:
        trace_event("ui.toolbar.new_project.open")

        async def _after_close() -> None:
            trace_event("ui.toolbar.new_project.after_close")
            await refresh_projects()

        await open_new_project_wizard(state, on_close=_after_close)

    async def on_check_updates() -> None:
        trace_event("ui.toolbar.check_updates.clicked")
        await run_update_check(state.settings, log_message)

    async def delete_project(project: ProjectStatus) -> None:
        trace_event("ui.project.delete.clicked", project=project.project_path, slug=project.metadata.slug)
        if runner.is_running:
            log_message("Delete project is unavailable while a command is running.")
            ui.notify("Stop the running command before deleting a project from the Manager.", type="warning")
            return
        ok = await confirm_dialog(
            title="Delete project from Manager",
            message=(
                f"Remove this project from the Manager project list?\n\n"
                f"{project.metadata.project_title}\n"
                f"slug: {project.metadata.slug}\n"
                f"path: {project.project_path}\n\n"
                "This only deletes the project from the Manager GUI data. It does not delete the folder, "
                "git repository, PHPP workbook, report files, or published site."
            ),
            confirm_label="Delete from Manager",
            danger=True,
        )
        if not ok:
            trace_event("ui.project.delete.cancelled", project=project.project_path)
            log_message("Delete project canceled.")
            return

        hidden_paths = _hidden_project_paths_with(state.settings.hidden_project_paths, project.project_path)
        state.settings = replace(state.settings, hidden_project_paths=hidden_paths)
        save_settings(state.settings)
        state.owned_lock_paths.discard(project.project_path)
        current = state.selected_project()
        if current is not None and current.project_path == project.project_path:
            state.selected_slug = None
            current_screen["name"] = "index"
        trace_event("ui.project.delete.saved", project=project.project_path, hidden_paths=hidden_paths)
        log_message(f"Deleted {project.metadata.slug} from Manager project list.")
        await refresh_projects()

    # ---- Lock refresh + shutdown -----------------------------------------
    async def refresh_owned_locks() -> None:
        refreshed_any = False
        for project_path in tuple(state.owned_lock_paths):
            lock = read_lock(project_path)
            if lock is None:
                state.owned_lock_paths.discard(project_path)
                continue
            if lock.malformed or not is_current_user_lock(lock):
                continue
            refresh_lock(project_path, state.settings.lock_ttl_hours)
            refreshed_any = True
        if refreshed_any:
            await refresh_projects()

    ui.timer(LOCK_REFRESH_INTERVAL_SECONDS, refresh_owned_locks)

    # Initial update check + project load via timers (preserves slot context)
    render_page()
    ui.timer(0.05, refresh_projects, once=True)
    ui.timer(0.25, on_check_updates, once=True)

    # ---- Keyboard shortcuts ----------------------------------------------
    def _on_key(e: Any) -> None:
        if not e.action.keydown:
            return
        meta = bool(getattr(e.modifiers, "meta", False) or getattr(e.modifiers, "ctrl", False))
        if not meta:
            return
        key = (getattr(e.key, "name", "") or "").lower()
        if key == "r":
            ui.timer(0, refresh_projects, once=True)
        elif key == ",":
            ui.timer(0, on_settings, once=True)
        elif key == "n":
            ui.timer(0, on_new_project, once=True)

    ui.keyboard(on_key=_on_key, repeating=False)

    # Register shutdown hook for this client's owned locks
    _register_shutdown_for(state, runner)


def _register_shutdown_for(state: ManagerState, runner: ProcessRunner) -> None:
    """Hook NiceGUI's shutdown to release locks owned by this process."""

    async def _shutdown() -> None:
        await runner.shutdown()
        for project_path in tuple(state.owned_lock_paths):
            lock = read_lock(project_path)
            if lock is not None and not lock.malformed and is_current_user_lock(lock):
                release_lock(project_path)
                state.owned_lock_paths.discard(project_path)

    app.on_shutdown(_shutdown)


def _hidden_project_paths_with(existing: tuple[Path, ...], project_path: Path) -> tuple[Path, ...]:
    resolved_project_path = project_path.expanduser().resolve()
    resolved_existing = {path.expanduser().resolve() for path in existing}
    if resolved_project_path in resolved_existing:
        return existing
    return (*existing, resolved_project_path)
