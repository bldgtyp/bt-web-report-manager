"""Application bootstrap.

Boots packaged .app builds in a pywebview window by default. Source runs use a
browser tab unless ``BTWR_MANAGER_NATIVE=1`` is set. Single-page app at ``/``;
there are no other routes.
"""

from __future__ import annotations

import multiprocessing
import os
import socket
import sys
from pathlib import Path

from nicegui import ui

from bt_web_report_manager.settings import load_settings
from bt_web_report_manager.ui.main import build_page
from bt_web_report_manager.ui.state import ManagerState

DEFAULT_PORT = 8765


def _pick_port() -> int:
    requested = os.environ.get("BTWR_MANAGER_PORT")
    if requested:
        try:
            return int(requested)
        except ValueError:
            pass
    # Prefer DEFAULT_PORT, fall back to an OS-picked free port if taken
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", DEFAULT_PORT))
        except OSError:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
        return DEFAULT_PORT


def _running_from_app_bundle(executable: Path | None = None) -> bool:
    current_executable = (executable or Path(sys.executable)).resolve()
    return any(
        parent.suffix == ".app" and (parent / "Contents" / "MacOS").is_dir() for parent in current_executable.parents
    )


def _native_window_enabled() -> bool:
    override = os.environ.get("BTWR_MANAGER_NATIVE")
    if override is not None:
        return override not in {"0", "false", "False", "no", "No"}
    return _running_from_app_bundle()


def run() -> int:
    multiprocessing.freeze_support()

    state = ManagerState(settings=load_settings())

    @ui.page("/")
    def index() -> None:
        build_page(state)

    native = _native_window_enabled()
    port = _pick_port()

    ui.run(
        title="bt-web-report Manager",
        favicon="🏠",
        port=port,
        reload=False,
        show=True,
        native=native,
        window_size=(1280, 820) if native else None,
        dark=False,
        storage_secret="bt-web-report-manager",
    )
    return 0


if __name__ in {"__main__", "__mp_main__"}:
    raise SystemExit(run())
