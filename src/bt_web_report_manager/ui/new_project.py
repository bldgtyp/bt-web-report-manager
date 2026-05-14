"""New-project wizard.

Three-step modal: Info → Preview → Build. Uses a NiceGUI ``ui.stepper`` so
the modal feeling is preserved without the dated QWizard chrome. The third
step either runs the ``btwr new`` bootstrap command (streaming output into a
local log) or shows the manual checklist when the CLI doesn't yet ship the
sub-command.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from nicegui import ui

from bt_web_report_manager.new_project import (
    NewProjectPlan,
    bootstrap_command,
    bootstrap_command_available,
    build_new_project_plan,
)
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
            "Slug fields drive sensible defaults — change any field after if you need to."
        ).classes("dialog-subtitle")

        info_fields: dict[str, Any] = {}
        preview_md: list[Any] = []
        build_log: list[Any] = []

        async def _build_plan_from_inputs() -> NewProjectPlan:
            phpp_text = (info_fields["phpp_path"].value or "").strip()
            return build_new_project_plan(
                project_title=info_fields["project_title"].value or "",
                slug=info_fields["slug"].value or "",
                client_name=info_fields["client_name"].value or None,
                building_name=info_fields["building_name"].value or None,
                phase=info_fields["phase"].value or None,
                local_folder=Path(info_fields["local_folder"].value or ""),
                target_web_path=Path(info_fields["target_web_path"].value or ""),
                phpp_path=Path(phpp_text) if phpp_text else None,
                repo_name=info_fields["repo_name"].value or "",
                repo_owner=state.settings.project_github_owner,
                production_url=info_fields["production_url"].value or "",
            )

        with ui.stepper().props("flat header-nav animated").classes("w-full mt-2") as stepper:
            # ---- Step 1: Info
            with ui.step("info", title="Project info", icon="edit_note"):
                with ui.column().classes("w-full gap-3 mt-2"):
                    with ui.row().classes("w-full gap-3"):
                        info_fields["project_title"] = (
                            ui.input("Project title", placeholder="29 Vandam Street")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip("Human-readable project title used in dashboards.")
                        )
                        info_fields["slug"] = (
                            ui.input("Slug", placeholder="vandam-29")
                            .props("outlined dense")
                            .classes("flex-1")
                            .tooltip("Lowercase kebab-case identifier. Drives subdomain, repo, and folder names.")
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

                    info_fields["local_folder"] = (
                        ui.input("Local folder", value=str(state.settings.projects_root / "Project Name"))
                        .props("outlined dense")
                        .classes("w-full")
                        .tooltip("Absolute path to the project folder. The 04_Web/ web folder will live inside it.")
                    )
                    info_fields["target_web_path"] = (
                        ui.input(
                            "Target 04_Web path",
                            value=str(state.settings.projects_root / "Project Name" / "04_Web"),
                        )
                        .props("outlined dense")
                        .classes("w-full")
                        .tooltip("Web folder Astro/bt-web-report-template clones into. Must end in 04_Web.")
                    )
                    info_fields["phpp_path"] = (
                        ui.input("PHPP workbook", placeholder="Optional absolute path to .xlsx or .xlsm")
                        .props("outlined dense")
                        .classes("w-full")
                        .tooltip("Optional — set later via project.yaml when the workbook is ready.")
                    )
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

                    def _sync_defaults() -> None:
                        slug = (info_fields["slug"].value or "").strip()
                        repo_val = (info_fields["repo_name"].value or "").strip()
                        if not repo_val or repo_val.startswith("bt-proj-"):
                            info_fields["repo_name"].set_value(f"bt-proj-{slug}" if slug else "")
                        url_val = (info_fields["production_url"].value or "").strip()
                        if not url_val or url_val.endswith(".bldgtyp.com"):
                            info_fields["production_url"].set_value(f"https://{slug}.bldgtyp.com" if slug else "")

                    def _sync_target() -> None:
                        local = (info_fields["local_folder"].value or "").strip()
                        target = (info_fields["target_web_path"].value or "").strip()
                        if target.endswith("/04_Web") or not target:
                            info_fields["target_web_path"].set_value(
                                str(Path(local).expanduser() / "04_Web") if local else ""
                            )

                    info_fields["slug"].on("update:model-value", lambda _e: _sync_defaults())
                    info_fields["local_folder"].on("update:model-value", lambda _e: _sync_target())

                with ui.stepper_navigation():

                    async def _go_preview() -> None:
                        try:
                            plan_ref["plan"] = await _build_plan_from_inputs()
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
