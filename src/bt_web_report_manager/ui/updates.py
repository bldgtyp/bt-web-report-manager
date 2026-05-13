"""Async update checker + update-available dialog."""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Callable

from nicegui import ui

from bt_web_report_manager import __version__
from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.updates import ReleaseInfo, UpdateCheckResult, check_for_updates


async def run_update_check(settings: ManagerSettings, log: Callable[[str], None]) -> None:
    """Check GitHub Releases; log status; if newer release exists, open dialog."""
    log("Checking GitHub Releases for manager updates...")
    result: UpdateCheckResult = await asyncio.to_thread(
        check_for_updates,
        settings.github_owner,
        settings.github_repo,
        __version__,
        3,
    )
    log(result.message)
    if result.ok and result.release is not None and result.release.is_update:
        await _show_update_dialog(result.release, log)


async def _show_update_dialog(release: ReleaseInfo, log: Callable[[str], None]) -> None:
    dialog = ui.dialog()
    with dialog, ui.card().classes("min-w-[480px]"):
        ui.label(f"Update available: {release.version}").classes("dialog-title")
        if release.name:
            ui.label(release.name).style("color: var(--text-2); font-size: 13px;")
        ui.element("div").style("height: 8px;")
        ui.label("Release page").classes("dialog-section-label")
        ui.label(release.url).classes("font-mono").style(
            "font-family: var(--font-mono); font-size: 12px; word-break: break-all; color: var(--text-2);"
        )
        if release.asset_name:
            ui.label("Asset").classes("dialog-section-label").style("margin-top: 8px;")
            ui.label(release.asset_name).style("font-family: var(--font-mono); font-size: 12px; color: var(--text-2);")

        with ui.row().classes("w-full justify-end items-center gap-2 mt-3"):
            ui.button("Later", on_click=dialog.close, color=None).props("flat unelevated no-caps").classes("action-btn")
            if release.asset_url:

                def _download() -> None:
                    webbrowser.open(release.asset_url or "")
                    log(f"Opening release asset: {release.asset_url}")
                    dialog.close()

                ui.button("Download asset", on_click=_download, color=None).props("flat unelevated no-caps").classes(
                    "action-btn"
                )

            def _open_release() -> None:
                webbrowser.open(release.url)
                log(f"Opening release page: {release.url}")
                dialog.close()

            ui.button("Open release page", on_click=_open_release, color=None).props("flat unelevated no-caps").classes(
                "action-btn is-primary"
            )
    await dialog
