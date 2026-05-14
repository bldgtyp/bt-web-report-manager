"""Settings / Doctor / confirm / prompt dialog helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from nicegui import ui

from bt_web_report_manager.commands import doctor
from bt_web_report_manager.models import ManagerSettings, ToolStatus
from bt_web_report_manager.settings import save_settings
from bt_web_report_manager.ui.state import ManagerState


async def confirm_dialog(
    *,
    title: str,
    message: str,
    confirm_label: str = "Continue",
    cancel_label: str = "Cancel",
    danger: bool = False,
) -> bool:
    """Modal confirm. Returns True iff the user clicked confirm."""
    dialog = ui.dialog().props("persistent")

    with dialog, ui.card().classes("min-w-[420px] max-w-[560px]"):
        ui.label(title).classes("dialog-title")
        ui.html(message.replace("\n", "<br>")).classes("text-sm").style(
            "color: var(--text-2); line-height: 1.5; white-space: pre-wrap;"
        )
        with ui.row().classes("w-full justify-end items-center gap-2 mt-2"):

            def _cancel() -> None:
                dialog.submit(False)

            def _ok() -> None:
                dialog.submit(True)

            ui.button(cancel_label, on_click=_cancel, color=None).props("flat unelevated no-caps").classes("action-btn")
            ui.button(confirm_label, on_click=_ok, color=None).props("flat unelevated no-caps autofocus").classes(
                "action-btn " + ("is-danger" if danger else "is-warning")
            )

    answer = await dialog
    return bool(answer)


async def prompt_dialog(
    *,
    title: str,
    label: str,
    default: str = "",
    placeholder: str = "",
    confirm_label: str = "OK",
) -> str | None:
    """Single-line text prompt. Returns None when canceled, the trimmed value otherwise."""
    dialog = ui.dialog().props("persistent")
    with dialog, ui.card().classes("min-w-[480px]"):
        ui.label(title).classes("dialog-title")
        ui.label(label).classes("text-xs").style("color: var(--text-2);")
        input_el = ui.input(value=default, placeholder=placeholder).props("outlined dense autofocus").classes("w-full")

        with ui.row().classes("w-full justify-end items-center gap-2"):

            def _cancel() -> None:
                dialog.submit(None)

            def _ok() -> None:
                dialog.submit(input_el.value or "")

            ui.button("Cancel", on_click=_cancel, color=None).props("flat unelevated no-caps").classes("action-btn")
            ui.button(confirm_label, on_click=_ok, color=None).props("flat unelevated no-caps").classes(
                "action-btn is-primary"
            )

        input_el.on("keydown.enter", _ok)

    answer = await dialog
    if answer is None:
        return None
    return str(answer).strip() or None


async def info_dialog(*, title: str, message: str, dismiss_label: str = "Close") -> None:
    dialog = ui.dialog()
    with dialog, ui.card().classes("min-w-[420px]"):
        ui.label(title).classes("dialog-title")
        ui.html(message.replace("\n", "<br>")).classes("text-sm").style(
            "color: var(--text-2); line-height: 1.5; white-space: pre-wrap;"
        )
        with ui.row().classes("w-full justify-end"):
            ui.button(dismiss_label, on_click=dialog.close, color=None).props("flat unelevated no-caps").classes(
                "action-btn is-primary"
            )
    await dialog


async def open_settings_dialog(state: ManagerState, on_save: Callable[[], Awaitable[None]] | None = None) -> None:
    """Show the settings dialog; persists on Save and triggers ``on_save``."""
    settings = state.settings
    dialog = ui.dialog().props("persistent")

    with dialog, ui.card().classes("min-w-[640px] max-w-[760px]"):
        ui.label("Settings").classes("dialog-title")
        ui.label(
            "Where the manager looks for projects and which tools it uses. Changes are saved to "
            "~/Library/Application Support/bt-web-report-manager/settings.yaml."
        ).classes("dialog-subtitle")

        with ui.column().classes("w-full gap-3 mt-2"):
            ui.label("Project discovery").classes("dialog-section-label")
            projects_root = (
                ui.input("Projects root", value=str(settings.projects_root))
                .props("outlined dense")
                .classes("w-full")
                .tooltip("Folder scanned for project directories. Each subfolder may contain 04_Web/ or 04_Web_next/.")
            )
            extra_paths = (
                ui.textarea(
                    "Extra project paths",
                    value="\n".join(str(p) for p in settings.extra_project_paths),
                    placeholder="One project path or project-root path per line",
                )
                .props("outlined dense autogrow")
                .classes("w-full")
                .tooltip(
                    "Additional paths to scan. Each line is either a project folder (with project.yaml) or a root."
                )
            )

            ui.label("Tools").classes("dialog-section-label")
            with ui.row().classes("w-full gap-3"):
                btwr_exe = (
                    ui.input("btwr executable", value=settings.btwr_executable)
                    .props("outlined dense")
                    .classes("flex-1")
                    .tooltip("Path or name of the bt-web-report CLI binary.")
                )
                pnpm_exe = (
                    ui.input("pnpm executable", value=settings.pnpm_executable)
                    .props("outlined dense")
                    .classes("flex-1")
                    .tooltip("Used for Dev preview (pnpm dev) and Open editor (pnpm dev:editor).")
                )
            with ui.row().classes("w-full gap-3"):
                git_exe = (
                    ui.input("git executable", value=settings.git_executable)
                    .props("outlined dense")
                    .classes("flex-1")
                    .tooltip("Used to read repo status and run commit/push.")
                )
                gh_exe = (
                    ui.input("gh executable", value=settings.gh_executable)
                    .props("outlined dense")
                    .classes("flex-1")
                    .tooltip("GitHub CLI; used by the New project bootstrap when available.")
                )
            editor_cmd = (
                ui.input("Code editor", value=settings.editor_command)
                .props("outlined dense")
                .classes("w-full")
                .tooltip("Executed by Open code editor, with the project path as its argument (e.g. 'code', 'cursor').")
            )

            ui.label("GitHub releases").classes("dialog-section-label")
            with ui.row().classes("w-full gap-3"):
                gh_owner = (
                    ui.input("GitHub owner", value=settings.github_owner)
                    .props("outlined dense")
                    .classes("flex-1")
                    .tooltip("Owner of the manager release repo. Defaults to bldgtyp.")
                )
                gh_repo = (
                    ui.input("GitHub repo", value=settings.github_repo)
                    .props("outlined dense")
                    .classes("flex-1")
                    .tooltip("Repo name to poll for manager updates.")
                )

            ui.label("Locks").classes("dialog-section-label")
            ttl = (
                ui.number(
                    "Lock TTL (hours)",
                    value=settings.lock_ttl_hours,
                    min=1,
                    max=48,
                    step=1,
                    format="%d",
                )
                .props("outlined dense")
                .classes("w-[160px]")
                .tooltip("How long a write lock survives before another user can take over without confirmation.")
            )

        with ui.row().classes("w-full justify-end items-center gap-2 mt-3"):
            ui.button("Cancel", on_click=lambda: dialog.submit(False), color=None).props(
                "flat unelevated no-caps"
            ).classes("action-btn")
            ui.button("Save", on_click=lambda: dialog.submit(True), color=None).props(
                "flat unelevated no-caps"
            ).classes("action-btn is-warning")

    accepted = await dialog
    if not accepted:
        return

    extra = tuple(Path(line.strip()).expanduser() for line in (extra_paths.value or "").splitlines() if line.strip())
    state.settings = ManagerSettings(
        projects_root=Path(projects_root.value or "~/Dropbox/bldgtyp").expanduser(),
        extra_project_paths=extra,
        btwr_executable=(btwr_exe.value or "btwr").strip(),
        pnpm_executable=(pnpm_exe.value or "pnpm").strip(),
        git_executable=(git_exe.value or "git").strip(),
        gh_executable=(gh_exe.value or "gh").strip(),
        editor_command=(editor_cmd.value or "code").strip(),
        github_owner=(gh_owner.value or "bldgtyp").strip(),
        github_repo=(gh_repo.value or "bt-web-report-manager").strip(),
        lock_ttl_hours=int(ttl.value or 4),
    )
    save_settings(state.settings)
    if on_save is not None:
        await on_save()


async def open_doctor_dialog(state: ManagerState) -> None:
    """Run setup checks and display results."""
    dialog = ui.dialog()

    statuses: list[ToolStatus] = await asyncio.to_thread(doctor, state.settings)

    with dialog, ui.card().classes("min-w-[760px] max-w-[920px]"):
        ui.label("Doctor").classes("dialog-title")
        ui.label("Read-only setup checks. Run this after editing Settings to confirm everything resolves.").classes(
            "dialog-subtitle"
        )

        with ui.column().classes("w-full gap-1 mt-2"):
            ui.element("div").classes("doctor-grid").style(
                "display: grid; grid-template-columns: 100px 90px 130px 1fr; "
                "gap: 6px 12px; font-family: var(--font-mono); font-size: 12px;"
            )
            with (
                ui.row()
                .classes("w-full px-1 py-2 items-center")
                .style(
                    "border-bottom: 1px solid var(--border-strong); font-size: 10px; "
                    "letter-spacing: 0.08em; text-transform: uppercase; "
                    "color: var(--text-muted); font-weight: 700;"
                )
            ):
                ui.label("Check").style("flex: 0 0 110px;")
                ui.label("Status").style("flex: 0 0 90px;")
                ui.label("Executable").style("flex: 0 0 140px;")
                ui.label("Path / message").style("flex: 1;")

            for status in statuses:
                chip_class = "chip chip-success" if status.ok else "chip chip-warning"
                chip_label = "OK" if status.ok else "Warning"
                with (
                    ui.row()
                    .classes("w-full px-1 py-2 items-start")
                    .style("border-bottom: 1px solid var(--border); font-family: var(--font-mono); font-size: 12px;")
                ):
                    ui.label(status.name).style("flex: 0 0 110px; font-weight: 600; color: var(--ink);")
                    with ui.element("div").style("flex: 0 0 90px;"):
                        ui.html(f'<span class="{chip_class}">{chip_label}</span>')
                    ui.label(status.executable).style("flex: 0 0 140px; color: var(--text-2); word-break: break-all;")
                    with ui.column().classes("gap-1").style("flex: 1; min-width: 0;"):
                        if status.path:
                            ui.label(status.path).style("color: var(--text); word-break: break-all;")
                        ui.label(status.message).style(
                            "color: var(--text-2); font-family: var(--font-sans); font-size: 12px;"
                        )

        with ui.row().classes("w-full justify-end mt-3"):
            ui.button("Close", on_click=dialog.close, color=None).props("flat unelevated no-caps").classes(
                "action-btn is-primary"
            )

    await dialog
