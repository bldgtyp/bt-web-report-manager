"""Async update checker + update-available dialog."""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Callable
from typing import Any

from nicegui import app, ui

from bt_web_report_manager import __version__
from bt_web_report_manager.models import ManagerSettings
from bt_web_report_manager.update_installer import (
    UpdateInstallError,
    current_app_bundle,
    is_installable_asset,
    launch_swap_helper,
    prepare_update,
    verify_update_app,
)
from bt_web_report_manager.updates import ReleaseInfo, UpdateCheckResult, check_for_updates

RETIRE_BROWSER_PAGE_SCRIPT = """
document.title = 'bt-web-report Manager updating';
document.body.innerHTML = `
  <main style="font: 15px -apple-system, BlinkMacSystemFont, sans-serif; padding: 32px;">
    <h1 style="font-size: 20px; margin: 0 0 8px;">bt-web-report Manager is updating</h1>
    <p style="color: #57534e; margin: 0;">The app is installing an update and relaunching. This tab can be closed.</p>
  </main>
`;
setTimeout(() => {
  window.close();
  setTimeout(() => window.location.replace('about:blank'), 250);
}, 100);
"""

UPDATE_PROGRESS_INITIAL_MESSAGE = "Downloading and verifying release asset..."
UPDATE_PROGRESS_INSTALLING_MESSAGE = "Installing and relaunching..."


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

                async def _install() -> None:
                    dialog.close()
                    await _download_and_install(release, log)

                ui.button("Download asset", on_click=_open_asset(release, log), color=None).props(
                    "flat unelevated no-caps"
                ).classes("action-btn")
                if is_installable_asset(release.asset_name):
                    ui.button("Install and relaunch", on_click=_install, color=None).props(
                        "flat unelevated no-caps"
                    ).classes("action-btn is-primary")

            def _open_release() -> None:
                webbrowser.open(release.url)
                log(f"Opening release page: {release.url}")
                dialog.close()

            ui.button("Open release page", on_click=_open_release, color=None).props("flat unelevated no-caps").classes(
                "action-btn"
            )
    await dialog


def _open_asset(release: ReleaseInfo, log: Callable[[str], None]) -> Callable[[], None]:
    def _download() -> None:
        webbrowser.open(release.asset_url or "")
        log(f"Opening release asset: {release.asset_url}")

    return _download


async def _download_and_install(release: ReleaseInfo, log: Callable[[str], None]) -> None:
    if not release.asset_url:
        log("Update install failed: release has no downloadable asset.")
        return

    current_app = current_app_bundle()
    if current_app is None:
        log("Update install unavailable: this process is not running from a packaged .app.")
        webbrowser.open(release.asset_url)
        return

    progress_dialog, progress_message = _open_update_progress_dialog(release.version)
    try:
        log(f"Downloading update asset: {release.asset_url}")
        prepared = await asyncio.to_thread(prepare_update, release.asset_url)
        log(f"Verifying update app: {prepared.extracted_app}")
        await asyncio.to_thread(verify_update_app, prepared.extracted_app)
        helper_path = await asyncio.to_thread(
            launch_swap_helper,
            current_app,
            prepared.extracted_app,
            cleanup_dir=prepared.temp_dir,
        )
    except UpdateInstallError as exc:
        progress_dialog.close()
        log(f"Update install failed: {exc}")
        ui.notify("Update install failed. Open the release page and install manually.", type="negative")
        return
    except Exception as exc:
        progress_dialog.close()
        log(f"Update install failed: {exc}")
        ui.notify("Update install failed. Open the release page and install manually.", type="negative")
        return

    log(f"Update helper started: {helper_path}")
    _set_update_progress_message(progress_message, UPDATE_PROGRESS_INSTALLING_MESSAGE)
    await _retire_current_browser_page(log)
    await asyncio.sleep(0.3)
    app.shutdown()


def _open_update_progress_dialog(version: str) -> tuple[Any, Any]:
    dialog = ui.dialog().props("persistent")
    with dialog, ui.card().classes("min-w-[420px]"):
        ui.label(f"Downloading update {version}").classes("dialog-title")
        ui.label("Preparing the new app. The manager will relaunch automatically.").classes("dialog-subtitle")
        ui.linear_progress().props("indeterminate rounded").style("margin-top: 14px;")
        progress_message = (
            ui.label(UPDATE_PROGRESS_INITIAL_MESSAGE).classes("dialog-section-label").style("margin-top: 14px;")
        )
    dialog.open()
    return dialog, progress_message


def _set_update_progress_message(progress_message: Any, message: str) -> None:
    progress_message.text = message


async def _retire_current_browser_page(log: Callable[[str], None]) -> None:
    try:
        await ui.run_javascript(RETIRE_BROWSER_PAGE_SCRIPT, timeout=0.2)
    except Exception:
        log("Browser tab close was not confirmed; the old tab may need to be closed manually.")
