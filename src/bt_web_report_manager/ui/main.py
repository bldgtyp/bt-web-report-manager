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
    client_building_label,
    commit_disabled_reason,
    format_dt,
    git_label,
    lock_label,
    lock_table_label,
    open_editor_disabled_reason,
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

    def log_message(text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log_widget = log_ref.get("widget")
        for line in text.splitlines() or [""]:
            stamped = f"[{ts}] {line}"
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

    # ---- Body -------------------------------------------------------------
    with ui.element("div").classes("app-body"):
        # ----- Left pane: summary + table
        with ui.element("div").classes("pane pane-left"):
            with ui.element("div").classes("pane-header"):
                ui.label("Projects").classes("pane-title")
                last_refresh = ui.label("").classes("pane-meta")
            summary_bar = ui.element("div").classes("summary-bar")
            project_table_container = ui.element("div").classes("project-table")

        # ----- Right pane: detail + actions + log
        with ui.element("div").classes("pane pane-right"):
            with ui.element("div").classes("pane-header"):
                ui.label("Active project").classes("pane-title")
                detail_kicker = ui.label("").classes("pane-meta")

            with ui.element("div").classes("detail-section"):
                detail_title = ui.label("No project selected").classes("detail-title")
                detail_subtitle = ui.label("Pick a row to see details and unlock actions.").classes("detail-subtitle")

            # Build the action cluster once; refresh only updates state/tooltip text.
            # Passing ``color=None`` to ``ui.button`` strips Quasar's default
            # ``bg-primary text-white`` / ``text-primary`` classes so our CSS controls
            # every paint surface. ``no-caps`` keeps the label readable.
            def _action_button(
                key: str,
                label: str,
                icon: str,
                handler: Any,
                modifier: str = "",
                tip_text: str | None = None,
            ) -> None:
                with (
                    ui.button(label, icon=icon, color=None, on_click=handler)
                    .props("flat unelevated no-caps")
                    .classes(f"action-btn {modifier}".strip()) as button
                ):
                    btn_tips[key] = ui.tooltip(tip_text or ACTIVE_TOOLTIPS[key])
                btns[key] = button

            with ui.element("div").classes("action-grid") as action_section:
                ui.label("Run").classes("action-group-label")
                _action_button("scrape", "Scrape PHPP", "travel_explore", lambda: run_scrape(), "is-warning")
                _action_button("dev", "Dev preview", "play_circle", lambda: run_dev_preview())

                ui.label("Author").classes("action-group-label")
                _action_button("editor", "Open editor (TinaCMS)", "edit_square", lambda: run_open_editor())
                _action_button("code_editor", "Open code editor", "code", lambda: run_open_code_editor())

                ui.label("Publish").classes("action-group-label")
                _action_button("commit", "Commit & push", "upload", lambda: run_commit_push(), "is-primary")
                _action_button("reveal", "Reveal in Finder", "folder_open", lambda: run_reveal())

                ui.label("Process").classes("action-group-label")
                _action_button("stop", "Stop", "stop_circle", lambda: on_stop(), "is-danger", "No command is running.")
                _action_button(
                    "copy_log",
                    "Copy log",
                    "content_copy",
                    lambda: on_copy_log(),
                    tip_text="Copy the action log to your clipboard.",
                )

            detail_body = (
                ui.element("div").classes("detail-section").style("overflow: auto; max-height: 320px; flex-shrink: 0;")
            )

            with ui.element("div").classes("log-shell"):
                with ui.element("div").classes("log-header"):
                    led = ui.element("div").classes("led idle")
                    ui.label("Action log").style("flex: 1;")
                log_widget = ui.log(max_lines=4000).classes("nicegui-log").style("flex: 1; min-height: 180px;")
                log_ref["widget"] = log_widget

    # ---- Helpers ----------------------------------------------------------
    def running_led_set(is_running: bool) -> None:
        led.classes(replace="led" if is_running else "led idle")

    def _badge_kind(badge: str) -> str:
        low = badge.lower()
        if low == "data current" or low == "git clean":
            return "success"
        if low.startswith("locked by you"):
            return "accent"
        if low.startswith("needs scrape") or low.startswith("dirty") or low.startswith("locked by"):
            return "warning"
        if "malformed" in low or "no data" in low or "no git" in low or "stale" in low or "warnings" in low:
            return "danger"
        return "neutral"

    def _badges_html(badges: tuple[str, ...]) -> str:
        return "".join(f'<span class="chip chip-{_badge_kind(b)}">{b}</span>' for b in badges)

    def _project_row(project: ProjectStatus) -> dict[str, Any]:
        return {
            "name": project.metadata.project_title,
            "slug": project.metadata.slug,
            "client_building": client_building_label(project),
            "phase": project.metadata.phase or "-",
            "phpp": format_dt(project.phpp_modified_at),
            "data": format_dt(project.manifest_generated_at),
            "git": git_label(project),
            "lock": lock_table_label(project),
            "deploy": "Unknown",
            "badges": ", ".join(project.badges),
            "badges_html": _badges_html(project.badges),
        }

    def render_summary_and_table() -> None:
        dirty = sum(1 for p in state.projects if p.git.dirty_count)
        needs_scrape = sum(1 for p in state.projects if p.needs_scrape)
        deploy_unknown = len(state.projects)
        total = len(state.projects)

        summary_bar.clear()
        with summary_bar:
            metrics = [
                ("Projects", total),
                ("Dirty git", dirty),
                ("Need scrape", needs_scrape),
                ("Deploy unknown", deploy_unknown),
            ]
            for i, (label, num) in enumerate(metrics):
                if i > 0:
                    ui.element("div").classes("divider")
                with ui.element("div").classes("metric"):
                    ui.html(f'<span class="num">{num}</span><span>{label}</span>')

        root_tag.content = f'<span style="color:#a8a29e;">root</span> &nbsp; {state.settings.projects_root}'
        last_refresh.text = f"Last scan {datetime.now().strftime('%H:%M:%S')}"

        project_table_container.clear()
        if not state.projects:
            with project_table_container:
                with ui.element("div").classes("empty-state"):
                    ui.html('<div style="font-size:28px;">📁</div>')
                    ui.label("No projects discovered").classes("empty-title")
                    ui.label(
                        "No project.yaml files were found under the configured projects root or extra "
                        "project paths. Open Settings to adjust the roots, then Refresh."
                    ).classes("empty-body")
            return

        columns = [
            {
                "name": "name",
                "label": "Name",
                "field": "name",
                "align": "left",
                "sortable": True,
                "style": "min-width: 140px;",
            },
            {
                "name": "slug",
                "label": "Slug",
                "field": "slug",
                "align": "left",
                "classes": "col-mono",
                "style": "min-width: 100px;",
            },
            {
                "name": "client_building",
                "label": "Client / Building",
                "field": "client_building",
                "align": "left",
                "style": "min-width: 160px;",
            },
            {"name": "phase", "label": "Phase", "field": "phase", "align": "left", "style": "min-width: 80px;"},
            {
                "name": "phpp",
                "label": "PHPP",
                "field": "phpp",
                "align": "left",
                "classes": "col-mono",
                "style": "min-width: 120px;",
            },
            {
                "name": "data",
                "label": "Data",
                "field": "data",
                "align": "left",
                "classes": "col-mono",
                "style": "min-width: 120px;",
            },
            {"name": "git", "label": "Git", "field": "git", "align": "left", "style": "min-width: 90px;"},
            {"name": "lock", "label": "Lock", "field": "lock", "align": "left", "style": "min-width: 80px;"},
            {"name": "deploy", "label": "Deploy", "field": "deploy", "align": "left", "style": "min-width: 80px;"},
            {
                "name": "badges",
                "label": "Status",
                "field": "badges",
                "align": "left",
                "style": "min-width: 180px; white-space: normal; max-width: none;",
            },
        ]
        rows = [_project_row(p) for p in state.projects]

        with project_table_container:
            table = (
                ui.table(
                    columns=columns,  # type: ignore[arg-type]
                    rows=rows,
                    row_key="slug",
                    selection="single",
                )
                .props("flat dense bordered")
                .classes("w-full")
            )

            table.add_slot(
                "body-cell-badges",
                r"""
                <q-td :props="props">
                    <span v-html="props.row.badges_html"></span>
                </q-td>
                """,
            )

            if state.selected_slug:
                table.selected = [r for r in rows if r["slug"] == state.selected_slug]

            def _on_select(_e: Any) -> None:
                if table.selected:
                    state.selected_slug = table.selected[0]["slug"]
                else:
                    state.selected_slug = None
                render_detail_pane()
                refresh_action_state()

            table.on("selection", _on_select)

    def render_detail_pane() -> None:
        project = state.selected_project()
        detail_body.clear()

        if project is None:
            detail_title.text = "No project selected"
            detail_subtitle.text = "Pick a row to see details and unlock actions."
            detail_kicker.text = ""
            return

        detail_title.text = project.metadata.project_title
        detail_subtitle.text = f"{project.metadata.slug} · {project.project_path}"
        detail_kicker.text = ", ".join(project.badges) or "—"

        with detail_body:
            with ui.element("div").classes("detail-section").style("padding: 0; border: none;"):
                ui.label("Project").classes("section-label")
                with ui.element("div").classes("kv-grid"):
                    _kv("Path", str(project.project_path))
                    _kv("Slug", project.metadata.slug)
                    _kv("Client", project.metadata.client_name or "-")
                    _kv("Building", project.metadata.building_name or "-")
                    _kv("URL", project.metadata.production_url or "-")
                    _kv("PHPP", str(project.metadata.phpp_path) if project.metadata.phpp_path else "-")
                    _kv("Manifest", str(project.manifest_path) if project.manifest_path else "-")

            with ui.element("div").classes("detail-section").style("padding: 14px 0 0 0;"):
                ui.label("State").classes("section-label")
                with ui.element("div").classes("kv-grid"):
                    _kv("Git", git_label(project))
                    _kv("Remote", project.git.remote or "-")
                    _kv("Last commit", project.git.last_commit or "-")
                    _kv("Lock", lock_label(project))
                    _kv("Deploy", "unknown (Cloudflare polling not wired in v1)")

            with ui.element("div").classes("detail-section").style("padding: 14px 0 0 0;"):
                ui.label("Status").classes("section-label")
                for line in status_explanations(project):
                    ui.label(line).style("font-size: 12.5px; color: var(--text-2); line-height: 1.55;")

            if project.warnings:
                with ui.element("div").classes("detail-section").style("padding: 14px 0 0 0;"):
                    ui.label("Warnings").classes("section-label")
                    for warning in project.warnings:
                        ui.label(f"- {warning}").style("font-size: 12.5px; color: var(--danger); line-height: 1.55;")

    def _kv(key: str, value: str) -> None:
        ui.html(f'<div class="k">{key}</div><div class="v">{value}</div>')

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
        state.select_first_if_unset()
        render_summary_and_table()
        render_detail_pane()
        refresh_action_state()

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
        widget = log_ref.get("widget")
        if widget is None:
            return
        lines = getattr(widget, "lines", None) or []
        text = "\n".join(lines)
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
