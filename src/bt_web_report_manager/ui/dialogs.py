"""Settings / system-check / confirm / prompt dialog helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path

from nicegui import ui

from bt_web_report_manager.commands import doctor
from bt_web_report_manager.models import ManagerSettings, ToolStatus
from bt_web_report_manager.settings import save_settings, workspace_btwr_executable
from bt_web_report_manager.trace import trace_event, trace_log_path
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
    trace_event("ui.confirm.open", title=title, confirm_label=confirm_label, cancel_label=cancel_label, danger=danger)
    dialog = ui.dialog().props("persistent")

    with dialog, ui.card().classes("min-w-[420px] max-w-[560px]"):
        ui.label(title).classes("dialog-title")
        ui.html(message.replace("\n", "<br>")).classes("text-sm").style(
            "color: var(--text-2); line-height: 1.5; white-space: pre-wrap;"
        )
        with ui.row().classes("w-full justify-end items-center gap-2 mt-2"):

            def _cancel() -> None:
                trace_event("ui.confirm.cancel", title=title)
                dialog.submit(False)

            def _ok() -> None:
                trace_event("ui.confirm.ok", title=title)
                dialog.submit(True)

            ui.button(cancel_label, on_click=_cancel, color=None).props("flat unelevated no-caps").classes("action-btn")
            ui.button(confirm_label, on_click=_ok, color=None).props("flat unelevated no-caps autofocus").classes(
                "action-btn " + ("is-danger" if danger else "is-warning")
            )

    answer = await dialog
    trace_event("ui.confirm.closed", title=title, answer=bool(answer))
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
    trace_event("ui.prompt.open", title=title, label=label, default=default, confirm_label=confirm_label)
    dialog = ui.dialog().props("persistent")
    with dialog, ui.card().classes("min-w-[480px]"):
        ui.label(title).classes("dialog-title")
        ui.label(label).classes("text-xs").style("color: var(--text-2);")
        input_el = ui.input(value=default, placeholder=placeholder).props("outlined dense autofocus").classes("w-full")

        with ui.row().classes("w-full justify-end items-center gap-2"):

            def _cancel() -> None:
                trace_event("ui.prompt.cancel", title=title)
                dialog.submit(None)

            def _ok() -> None:
                trace_event("ui.prompt.ok", title=title, value=input_el.value or "")
                dialog.submit(input_el.value or "")

            ui.button("Cancel", on_click=_cancel, color=None).props("flat unelevated no-caps").classes("action-btn")
            ui.button(confirm_label, on_click=_ok, color=None).props("flat unelevated no-caps").classes(
                "action-btn is-primary"
            )

        input_el.on("keydown.enter", _ok)

    answer = await dialog
    if answer is None:
        trace_event("ui.prompt.closed", title=title, answer=None)
        return None
    value = str(answer).strip() or None
    trace_event("ui.prompt.closed", title=title, answer=value)
    return value


async def info_dialog(*, title: str, message: str, dismiss_label: str = "Close") -> None:
    trace_event("ui.info.open", title=title, dismiss_label=dismiss_label)
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
    trace_event("ui.settings.open", settings=state.settings, trace_log_path=trace_log_path())
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

            ui.label("Project repositories").classes("dialog-section-label")
            project_gh_owner = (
                ui.input("Project GitHub owner", value=settings.project_github_owner)
                .props("outlined dense")
                .classes("w-full")
                .tooltip("Owner/org for per-project bt-proj-* repos. Defaults to bldgtyp-projects.")
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
        trace_event("ui.settings.cancel")
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
        project_github_owner=(project_gh_owner.value or "bldgtyp-projects").strip(),
        lock_ttl_hours=int(ttl.value or 4),
    )
    save_settings(state.settings)
    trace_event("ui.settings.saved", settings=state.settings)
    if on_save is not None:
        await on_save()


async def open_doctor_dialog(state: ManagerState) -> None:
    """Run setup checks and display results."""
    trace_event("ui.doctor.open", settings=state.settings, trace_log_path=trace_log_path())
    dialog = ui.dialog()

    statuses: list[ToolStatus] = await asyncio.to_thread(doctor, state.settings)
    workspace_btwr = workspace_btwr_executable()
    trace_event(
        "ui.doctor.statuses_loaded",
        statuses=[
            {"name": status.name, "ok": status.ok, "path": status.path, "message": status.message}
            for status in statuses
        ],
        workspace_btwr=workspace_btwr,
    )

    with dialog, ui.card().classes("min-w-[760px] max-w-[920px]"):
        ui.label("System Check").classes("dialog-title")
        ui.label("Setup checks. Use the repair action when available, then rerun System Check to confirm.").classes(
            "dialog-subtitle"
        )
        ui.label(f"Trace log: {trace_log_path()}").style(
            "font-family: var(--font-mono); font-size: 11px; color: var(--text-2); word-break: break-all;"
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
                        if _can_repair_btwr(status, workspace_btwr):
                            repair_path = workspace_btwr or ""
                            ui.label(f"Suggested path: {repair_path}").style(
                                "color: var(--text); font-family: var(--font-mono); font-size: 11px; word-break: break-all;"
                            )

                            def _repair_btwr(path: str = repair_path) -> None:
                                trace_event("ui.doctor.repair_btwr.clicked", path=path)
                                state.settings = replace(state.settings, btwr_executable=path)
                                save_settings(state.settings)
                                ui.notify("Saved workspace btwr path. Rerun System Check to confirm.", type="positive")
                                dialog.close()

                            ui.button("Use workspace btwr", on_click=_repair_btwr, color=None).props(
                                "flat unelevated no-caps"
                            ).classes("action-btn is-warning").style("align-self: flex-start; margin-top: 4px;")

        async def _open_setup_guide() -> None:
            trace_event("ui.doctor.setup_guide.clicked")
            await open_partner_setup_dialog(state)

        def _close_doctor() -> None:
            trace_event("ui.doctor.close.clicked")
            dialog.close()

        with ui.row().classes("w-full justify-between mt-3"):
            ui.button(
                "Setup guide",
                on_click=_open_setup_guide,
                color=None,
            ).props(
                "flat unelevated no-caps"
            ).classes("action-btn")
            ui.button(
                "Close",
                on_click=_close_doctor,
                color=None,
            ).props(
                "flat unelevated no-caps"
            ).classes("action-btn is-primary")

    await dialog


def _can_repair_btwr(status: ToolStatus, workspace_btwr: str | None) -> bool:
    return bool(status.name == "btwr" and not status.ok and workspace_btwr and status.executable != workspace_btwr)


async def open_partner_setup_dialog(state: ManagerState) -> None:
    trace_event("ui.partner_setup.open", settings=state.settings)
    dialog = ui.dialog()
    with dialog, ui.card().classes("min-w-[760px] max-w-[920px]"):
        ui.label("Partner setup guide").classes("dialog-title")
        ui.label("Use this when installing bt-web-report Manager on another BLDGTYP Mac.").classes("dialog-subtitle")
        ui.markdown(_partner_setup_markdown(state)).classes("w-full").style(
            "font-size: 13px; line-height: 1.45; max-height: 560px; overflow: auto;"
        )
        with ui.row().classes("w-full justify-end mt-3"):
            ui.button("Close", on_click=dialog.close, color=None).props("flat unelevated no-caps").classes(
                "action-btn is-primary"
            )
    await dialog


def _partner_setup_markdown(state: ManagerState) -> str:
    settings = state.settings
    workspace_btwr = workspace_btwr_executable()
    suggested_btwr = workspace_btwr or settings.btwr_executable
    return f"""
### What John needs to do

1. **Install the Manager app.**
   - Download the latest `bt-web-report-manager-<version>.zip` from the `bldgtyp/bt-web-report-manager` GitHub Release.
   - Unzip it, move `bt-web-report Manager.app` to `/Applications`, then open it once.

2. **Confirm Dropbox project access.**
   - Dropbox must sync the shared BLDGTYP project root at `~/Dropbox/bldgtyp`.
   - The Manager scans this root for project folders containing `04_Web/project.yaml`.

3. **Install the command-line tools the app wraps.**
   - Install Apple Command Line Tools if `git` is missing: `xcode-select --install`.
   - Install Homebrew if needed.
   - Install runtime tools: `brew install pnpm gh`.
   - Install VS Code's `code` command from VS Code: Command Palette -> `Shell Command: Install 'code' command in PATH`.

4. **Authenticate GitHub.**
   - Run `gh auth login`.
   - John needs access to `bldgtyp/bt-web-report-manager`, platform repos under `bldgtyp`, and project repos under `bldgtyp-projects`.
   - Verify with `gh auth status`.

5. **Provide a `btwr` CLI executable.**
   - Current internal builds shell out to `btwr`; the `.app` does not yet bundle the CLI.
   - For the shared dev workspace, use: `{suggested_btwr}`.
   - If John's workspace lives somewhere else, set **Settings -> btwr executable** to his local `.venv/bin/btwr`.
   - Future packaging should either bundle `btwr` or install it as a managed companion tool.

6. **Run System Check.**
   - Open **System Check** in the Manager.
   - All rows should be green before running project actions.
   - If `btwr` is missing and the workspace CLI is detected, click **Use workspace btwr**, then rerun System Check.

7. **Smoke-test one project.**
   - Click **Refresh**.
   - Open a known project.
   - Use non-destructive actions first: Reveal in Finder, Dev preview, Stop.
   - Only use Commit & push after confirming the correct repo and branch.

### Current settings on this Mac

- Projects root: `{settings.projects_root}`
- btwr executable: `{settings.btwr_executable}`
- pnpm executable: `{settings.pnpm_executable}`
- git executable: `{settings.git_executable}`
- gh executable: `{settings.gh_executable}`
- code editor: `{settings.editor_command}`
"""
