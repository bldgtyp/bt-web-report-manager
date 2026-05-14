"""New-project wizard.

Three-step modal: Info → Preview → Build. Uses a NiceGUI ``ui.stepper`` so
the modal feeling is preserved without the dated QWizard chrome. The third
step either runs the ``btwr new`` bootstrap command (streaming output into a
local log) or shows the manual checklist when the CLI doesn't yet ship the
sub-command.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from nicegui import ui

from bt_web_report_manager.new_project import (
    NewProjectPlan,
    bootstrap_command,
    bootstrap_command_available,
    build_new_project_plan,
    clean_path_text,
    default_slug_from_project_folder,
    meaningful_existing_items,
    production_url_from_slug,
    repo_name_from_slug,
    sanitize_slug,
)
from bt_web_report_manager.ui.dialogs import confirm_dialog
from bt_web_report_manager.ui.runner import ProcessRunner
from bt_web_report_manager.ui.state import ManagerState


async def open_new_project_wizard(
    state: ManagerState,
    on_close: Callable[[], Awaitable[None]],
) -> None:
    """Open the wizard. ``on_close`` is awaited after the dialog dismisses."""
    plan_ref: dict[str, NewProjectPlan | None] = {"plan": None}

    dialog = ui.dialog().props("persistent")

    def _close() -> None:
        dialog.submit(False)

    with dialog, ui.card().classes("min-w-[860px] max-w-[920px]").style("padding: 16px 20px;"):
        ui.label("New project").classes("dialog-title")
        ui.label(
            "Three steps: enter project info, confirm the derived plan, then bootstrap. "
            "Pick the local project folder first; defaults are derived from the BT number when possible."
        ).classes("dialog-subtitle")

        info_fields: dict[str, Any] = {}
        preview_md: list[Any] = []
        build_log: list[Any] = []
        auto_fields = {"slug": True, "target": True, "repo": True, "url": True}
        programmatic_update = {"active": False}

        async def _build_plan_from_inputs(*, overwrite_existing: bool = False) -> NewProjectPlan:
            _sync_all_defaults()
            phpp_text = clean_path_text(info_fields["phpp_path"].value or "")
            return build_new_project_plan(
                project_title=info_fields["project_title"].value or "",
                slug=info_fields["slug"].value or "",
                client_name=info_fields["client_name"].value or None,
                building_name=info_fields["building_name"].value or None,
                phase=info_fields["phase"].value or None,
                local_folder=clean_path_text(info_fields["local_folder"].value or ""),
                target_web_path=clean_path_text(info_fields["target_web_path"].value or ""),
                phpp_path=phpp_text if phpp_text else None,
                repo_name=info_fields["repo_name"].value or "",
                repo_owner=state.settings.project_github_owner,
                production_url=info_fields["production_url"].value or "",
                overwrite_existing=overwrite_existing,
            )

        async def _confirm_overwrite_if_needed() -> bool:
            target = Path(clean_path_text(info_fields["target_web_path"].value or "")).expanduser()
            existing_items = meaningful_existing_items(target)
            if not existing_items:
                return False
            item_lines = "\n".join(f"- {item.name}" for item in existing_items[:8])
            if len(existing_items) > 8:
                item_lines += f"\n- and {len(existing_items) - 8} more"
            ok = await confirm_dialog(
                title="Overwrite existing 04_Web contents?",
                message=(
                    f"{target} already contains project files:\n\n"
                    f"{item_lines}\n\n"
                    "Continuing will replace this folder's contents during bootstrap."
                ),
                confirm_label="Overwrite 04_Web",
                cancel_label="Go back",
                danger=True,
            )
            return ok

        def _set_field(name: str, value: str) -> None:
            if (info_fields[name].value or "") == value:
                return
            programmatic_update["active"] = True
            try:
                info_fields[name].set_value(value)
            finally:
                programmatic_update["active"] = False

        def _normalize_path_field(name: str) -> str:
            cleaned = clean_path_text(info_fields[name].value or "")
            if cleaned != (info_fields[name].value or ""):
                _set_field(name, cleaned)
            return cleaned

        def _sync_defaults_from_slug(slug: str) -> None:
            clean_slug = sanitize_slug(slug)
            if auto_fields["repo"]:
                _set_field("repo_name", repo_name_from_slug(clean_slug))
            if auto_fields["url"]:
                _set_field("production_url", production_url_from_slug(clean_slug))

        def _sync_from_local_folder() -> None:
            local = _normalize_path_field("local_folder")
            if not local:
                return
            target = _normalize_path_field("target_web_path")
            if auto_fields["target"] or not target:
                _set_field("target_web_path", str(Path(local).expanduser() / "04_Web"))
            current_slug = sanitize_slug(info_fields["slug"].value or "")
            if auto_fields["slug"] or not current_slug:
                default_slug = default_slug_from_project_folder(local)
                _set_field("slug", default_slug)
                _sync_defaults_from_slug(default_slug)
            else:
                _sync_defaults_from_slug(current_slug)

        def _sync_all_defaults() -> None:
            _sync_from_local_folder()
            slug = sanitize_slug(info_fields["slug"].value or "")
            if slug != (info_fields["slug"].value or ""):
                _set_field("slug", slug)
            _sync_defaults_from_slug(slug)

        async def _choose_directory(target_field: str) -> None:
            current = clean_path_text(info_fields[target_field].value or "")
            initial = Path(current).expanduser() if current else state.settings.projects_root
            if not initial.exists():
                initial = state.settings.projects_root
            if initial.is_file():
                initial = initial.parent
            selected = await _run_macos_picker(
                f'POSIX path of (choose folder with prompt "Choose project folder" default location POSIX file "{_applescript_escape(str(initial))}")'
            )
            if selected:
                _set_field(target_field, selected.rstrip("/"))
                _sync_from_local_folder()

        async def _choose_phpp() -> None:
            current = clean_path_text(info_fields["phpp_path"].value or "")
            local = clean_path_text(info_fields["local_folder"].value or "")
            initial = Path(current or local or state.settings.projects_root).expanduser()
            if initial.is_file():
                initial = initial.parent
            if not initial.exists():
                initial = state.settings.projects_root
            selected = await _run_macos_picker(
                f'POSIX path of (choose file with prompt "Choose PHPP workbook" default location POSIX file "{_applescript_escape(str(initial))}")'
            )
            if selected:
                _set_field("phpp_path", selected)

        async def _choose_local_directory() -> None:
            await _choose_directory("local_folder")

        with ui.stepper().props("flat header-nav animated").classes("w-full mt-2") as stepper:
            # ---- Step 1: Info
            with ui.step("info", title="Project info", icon="edit_note"):
                with ui.column().classes("w-full gap-3 mt-2"):
                    with ui.row().classes("w-full gap-2 items-center"):
                        info_fields["local_folder"] = (
                            ui.input("Local folder", value=str(state.settings.projects_root / "Project Name"))
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip(
                                "Absolute path to the BT project folder. Paste Finder Copy as Pathname values directly; enclosing quotes are stripped."
                            )
                        )
                        ui.button(icon="folder_open", on_click=_choose_local_directory, color=None).props(
                            "flat unelevated"
                        ).classes("action-btn icon-only").tooltip("Choose local project folder")
                    info_fields["target_web_path"] = (
                        ui.input(
                            "Target 04_Web path",
                            value=str(state.settings.projects_root / "Project Name" / "04_Web"),
                        )
                        .props("outlined dense")
                        .classes("w-full")
                        .tooltip("Web folder created inside the project folder. Must end in 04_Web.")
                    )
                    with ui.row().classes("w-full gap-3"):
                        info_fields["project_title"] = (
                            ui.input("Project title", placeholder="29 Vandam Street")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip("Human-readable project title used in dashboards.")
                        )
                        info_fields["slug"] = (
                            ui.input("Slug name", placeholder="project-2606")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip(
                                "Stable lowercase ID for the report. It drives the repo name and production subdomain; default is project-<BT number> from the local folder."
                            )
                        )
                    with ui.row().classes("w-full gap-3"):
                        info_fields["client_name"] = ui.input("Client").props("outlined dense").classes("flex-1")
                        info_fields["building_name"] = ui.input("Building").props("outlined dense").classes("flex-1")
                        info_fields["phase"] = (
                            ui.input("Phase", value="Design Analysis")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip("Project phase label, e.g. Design Analysis or PH Certification.")
                        )

                    with ui.row().classes("w-full gap-2 items-center"):
                        info_fields["phpp_path"] = (
                            ui.input("PHPP workbook", placeholder="Optional absolute path to .xlsx or .xlsm")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip("Optional — set later via project.yaml when the workbook is ready.")
                        )
                        ui.button(icon="description", on_click=_choose_phpp, color=None).props(
                            "flat unelevated"
                        ).classes("action-btn icon-only").tooltip("Choose PHPP workbook")
                    with ui.row().classes("w-full gap-3"):
                        info_fields["repo_name"] = (
                            ui.input("Repo name")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip(
                                f"Will be created under {state.settings.project_github_owner}/. Format: bt-proj-<slug>."
                            )
                        )
                        info_fields["production_url"] = (
                            ui.input("Production URL", placeholder="https://<slug>.bldgtyp.com")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip("Final Cloudflare Pages origin. https://<slug>.bldgtyp.com")
                        )

                    def _on_slug_change() -> None:
                        if not programmatic_update["active"]:
                            auto_fields["slug"] = False
                        slug = sanitize_slug(info_fields["slug"].value or "")
                        if slug != (info_fields["slug"].value or ""):
                            _set_field("slug", slug)
                        _sync_defaults_from_slug(slug)

                    def _on_local_folder_change() -> None:
                        if not programmatic_update["active"]:
                            _sync_from_local_folder()

                    def _mark_manual(name: str) -> None:
                        if not programmatic_update["active"]:
                            auto_fields[name] = False

                    info_fields["slug"].on("update:model-value", lambda _e: _on_slug_change())
                    info_fields["local_folder"].on("update:model-value", lambda _e: _on_local_folder_change())
                    info_fields["target_web_path"].on("update:model-value", lambda _e: _mark_manual("target"))
                    info_fields["repo_name"].on("update:model-value", lambda _e: _mark_manual("repo"))
                    info_fields["production_url"].on("update:model-value", lambda _e: _mark_manual("url"))
                    info_fields["phpp_path"].on("update:model-value", lambda _e: _normalize_path_field("phpp_path"))
                    _sync_from_local_folder()

                with ui.stepper_navigation():

                    async def _go_preview() -> None:
                        try:
                            overwrite = await _confirm_overwrite_if_needed()
                            if (
                                meaningful_existing_items(
                                    Path(clean_path_text(info_fields["target_web_path"].value or "")).expanduser()
                                )
                                and not overwrite
                            ):
                                return
                            plan_ref["plan"] = await _build_plan_from_inputs(overwrite_existing=overwrite)
                        except ValueError as exc:
                            ui.notify(str(exc), type="warning", multi_line=True, timeout=8000)
                            return
                        plan = plan_ref["plan"]
                        if preview_md and plan is not None:
                            preview_md[0].content = "\n".join(
                                f"- **{line.split(':', 1)[0]}**:{line.split(':', 1)[1]}" if ":" in line else f"- {line}"
                                for line in plan.summary_lines()
                            )
                        stepper.next()

                    ui.button("Cancel", on_click=_close, color=None).props("flat unelevated no-caps").classes(
                        "action-btn"
                    )
                    ui.button("Preview →", on_click=_go_preview, color=None).props("flat unelevated no-caps").classes(
                        "action-btn is-warning"
                    )

            # ---- Step 2: Preview
            with ui.step("preview", title="Preview", icon="visibility"):
                ui.label("Confirm the plan").classes("dialog-section-label").style("margin-top: 4px;")
                preview_md.append(
                    ui.markdown("_Build the plan from the previous step first._")
                    .classes("w-full p-3 rounded")
                    .style("background: var(--surface-2); border: 1px solid var(--border); font-size: 13px;")
                )
                ui.label(
                    "If the bt-web-report CLI ships the `new` sub-command, the next step bootstraps "
                    "automatically. Otherwise you'll see the manual checklist."
                ).style("font-size: 12px; color: var(--text-2); margin-top: 4px;")

                with ui.stepper_navigation():
                    ui.button("← Back", on_click=stepper.previous, color=None).props("flat unelevated no-caps").classes(
                        "action-btn"
                    )
                    ui.button("Build →", on_click=stepper.next, color=None).props("flat unelevated no-caps").classes(
                        "action-btn is-warning"
                    )

            # ---- Step 3: Build
            with ui.step("build", title="Build", icon="rocket_launch"):
                ui.label("Bootstrap log").classes("dialog-section-label").style("margin-top: 4px;")
                log = ui.log(max_lines=2000).classes("w-full nicegui-log").style("height: 280px;")
                build_log.append(log)

                async def _start_build() -> None:
                    plan = plan_ref["plan"]
                    if plan is None:
                        log.push("[error] no plan available — go back to step 1 and retry.")
                        return
                    log.clear()
                    for line in plan.summary_lines():
                        log.push(f"[plan] {line}")
                    log.push("")
                    if bootstrap_command_available(state.settings):
                        spec = bootstrap_command(plan, state.settings)
                        log.push(f"[run] $ {' '.join(spec.args)}")
                        finished = asyncio.Event()

                        def on_log(line: str) -> None:
                            log.push(line)

                        def on_done(_name: str, code: int, _refresh: bool, canceled: bool) -> None:
                            if canceled:
                                log.push("[stopped]")
                            else:
                                log.push(f"[exit {code}]")
                            finished.set()

                        runner = ProcessRunner(on_log=on_log, on_done=on_done)
                        await runner.start(spec)
                        await finished.wait()
                    else:
                        log.push("[info] btwr new is not available in the configured CLI. Manual checklist:")
                        log.push("")
                        for line in plan.manual_checklist():
                            log.push(line)

                with ui.stepper_navigation():
                    ui.button("← Back", on_click=stepper.previous, color=None).props("flat unelevated no-caps").classes(
                        "action-btn"
                    )
                    ui.button("Run bootstrap", on_click=_start_build, color=None).props(
                        "flat unelevated no-caps"
                    ).classes("action-btn is-warning")
                    ui.button("Close", on_click=_close, color=None).props("flat unelevated no-caps").classes(
                        "action-btn is-primary"
                    )

    await dialog
    await on_close()


async def _run_macos_picker(script: str) -> str | None:
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["osascript", "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        ui.notify(f"File picker failed: {exc}", type="warning", multi_line=True)
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _applescript_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
