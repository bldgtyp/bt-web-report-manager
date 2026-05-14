"""Main manager page.

Renders the toolbar, project table, detail pane, action cluster, and log.
Owns the ``ProcessRunner``, lock-refresh timer, and shutdown hook for
releasing locks. All UI state lives in ``ManagerState`` (in ``state.py``).
"""

from __future__ import annotations

import asyncio
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
from bt_web_report_manager.ui.runner import ProcessRunner
from bt_web_report_manager.ui.state import ManagerState
from bt_web_report_manager.ui.theme import apply_theme
from bt_web_report_manager.ui.updates import run_update_check

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
    apply_theme()

    # Mutable refs filled in during construction below
    log_ref: dict[str, Any] = {}
    btns: dict[str, Any] = {}
    btn_tips: dict[str, Any] = {}
    led_ref: dict[str, Any] = {}
    log_lines: list[str] = []
    current_screen = {"name": "index"}

    def log_message(text: str) -> None:
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
        log_message(line)

    def on_runner_done(name: str, exit_code: int, refresh_on_success: bool, canceled: bool) -> None:
        if canceled:
            log_message(f"{name} stopped by user.")
        else:
            log_message(f"{name} finished with exit code {exit_code}.")
        # Schedule the UI update via a timer so the slot context is preserved
        ui.timer(0, lambda: _post_command_refresh(refresh_on_success and exit_code == 0 and not canceled), once=True)

    def _post_command_refresh(do_refresh: bool) -> None:
        running_led_set(False)
        if do_refresh:
            ui.timer(0, refresh_projects, once=True)
        else:
            refresh_action_state()

    runner = ProcessRunner(on_log=on_runner_log, on_done=on_runner_done)

    # ---- Header / toolbar -------------------------------------------------
    with ui.element("div").classes("app-header"):
        with ui.element("div").classes("brand"):
            ui.html('<span class="brand-mark">bt</span>')
            ui.label("bt-web-report Manager")
            ui.label(f"v{__version__}").style(
                "color: #a8a29e; font-family: var(--font-mono); font-size: 11px; margin-left: 6px;"
            )

        def _tool_button(label: str, icon: str, handler: Any, modifier: str, tip: str) -> None:
            with (
                ui.button(label, icon=icon, color=None, on_click=handler)
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
                    for label in ("Name", "Slug", "Client / Building", "Phase", "PHPP", "Data", "Git", "Status"):
                        ui.label(label)
                for project in state.projects:
                    row = project_row(project)
                    with (
                        ui.element("button")
                        .classes("project-list-row")
                        .on("click", lambda _e, slug=project.metadata.slug: open_workspace(slug))
                    ):
                        ui.label(row["name"]).classes("project-cell project-name")
                        ui.label(row["slug"]).classes("project-cell col-mono")
                        ui.label(row["client_building"]).classes("project-cell")
                        ui.label(row["phase"]).classes("project-cell")
                        ui.label(row["phpp"]).classes("project-cell col-mono")
                        ui.label(row["data"]).classes("project-cell col-mono")
                        ui.label(row["git"]).classes("project-cell")
                        ui.html(row["badges_html"]).classes("project-cell project-status-cell")

    def open_workspace(slug: str) -> None:
        state.selected_slug = slug
        current_screen["name"] = "workspace"
        render_page()

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
        with (
            ui.button(color=None, on_click=handler)
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
        with ui.element("div").classes("info-panel files-panel"):
            with ui.element("div").classes("panel-header"):
                ui.label("Files & locations").classes("panel-title")
                ui.button(
                    "Copy paths", icon="content_copy", color=None, on_click=lambda: copy_project_paths(project)
                ).props("flat dense unelevated no-caps").classes("panel-tool")
            for location in project_file_locations(project):
                with ui.element("div").classes("file-row"):
                    ui.label(location.kind).classes(f"file-kind file-kind-{location.kind.lower()}")
                    with ui.element("div").classes("file-main"):
                        ui.label(location.label).classes("file-label")
                        ui.label(location.value).classes("file-value")
                    ui.button(
                        icon="content_copy", color=None, on_click=lambda loc=location: copy_text(loc.value)
                    ).props("flat dense round").classes("icon-tool")

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
        selected_path = preserve_path
        if selected_path is None:
            current = state.selected_project()
            if current is not None:
                selected_path = current.project_path

        state.projects = await asyncio.to_thread(discover_projects, state.settings)
        state.select_project_by_path(selected_path)
        render_page()

    async def prepare_mutating_action(project: ProjectStatus) -> bool:
        lock = read_lock(project.project_path)
        if lock_requires_confirmation(lock):
            assert lock is not None
            ok = await confirm_dialog(
                title="Project lock",
                message=lock_warning_message(lock),
                confirm_label="Continue and overwrite",
                danger=True,
            )
            if not ok:
                log_message("Action canceled because the project is locked.")
                return False
        write_lock(project.project_path, project.metadata.slug, state.settings.lock_ttl_hours)
        state.owned_lock_paths.add(project.project_path)
        log_message(f"Lock refreshed for {project.metadata.slug}.")
        await refresh_projects(project.project_path)
        return True

    async def _start_command(spec: CommandSpec) -> None:
        running_led_set(True)
        refresh_action_state()
        await runner.start(spec)

    async def run_scrape() -> None:
        project = state.selected_project()
        if project is None:
            return
        if await prepare_mutating_action(project):
            await _start_command(scrape_command(project, state.settings))

    async def run_dev_preview() -> None:
        project = state.selected_project()
        if project is None:
            return
        if await prepare_mutating_action(project):
            await _start_command(dev_preview_command(project, state.settings))

    async def run_open_editor() -> None:
        project = state.selected_project()
        if project is None:
            return
        if await prepare_mutating_action(project):
            await _start_command(open_editor_command(project, state.settings))

    async def run_open_code_editor() -> None:
        project = state.selected_project()
        if project is not None:
            await _start_command(open_code_editor_command(project, state.settings))

    async def run_reveal() -> None:
        project = state.selected_project()
        if project is not None:
            await _start_command(reveal_command(project))

    async def run_commit_push() -> None:
        project = state.selected_project()
        if project is None or not project.git.is_repo or project.git.dirty_count == 0:
            log_message("Commit & push requires a dirty git worktree.")
            return
        message = await prompt_dialog(
            title="Commit & push",
            label="Commit message",
            default=suggest_commit_message(project),
            confirm_label="Next",
        )
        if not message:
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
            log_message("Commit & push canceled before running git.")
            return
        if await prepare_mutating_action(project):
            await _start_command(commit_push_command(project, state.settings, message))

    def on_stop() -> None:
        runner.stop()

    def on_copy_log() -> None:
        text = "\n".join(log_lines)
        try:
            pyperclip.copy(text)
            log_message("Action log copied to clipboard.")
        except pyperclip.PyperclipException as exc:
            log_message(f"Clipboard unavailable: {exc}")
            ui.notify("Clipboard unavailable on this machine.", type="warning")

    async def on_settings() -> None:
        async def _after_save() -> None:
            log_message("Settings saved and project list refreshed.")
            await refresh_projects()

        await open_settings_dialog(state, on_save=_after_save)

    async def on_doctor() -> None:
        await open_doctor_dialog(state)

    async def on_new_project() -> None:
        async def _after_close() -> None:
            await refresh_projects()

        await open_new_project_wizard(state, on_close=_after_close)

    async def on_check_updates() -> None:
        await run_update_check(state.settings, log_message)

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
