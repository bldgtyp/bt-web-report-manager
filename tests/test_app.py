from __future__ import annotations

from pathlib import Path

import pytest

from bt_web_report_manager import app


def test_native_window_override_enables_native(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BTWR_MANAGER_NATIVE", "1")

    assert app._native_window_enabled()


def test_native_window_override_disables_native(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BTWR_MANAGER_NATIVE", "0")

    assert not app._native_window_enabled()


def test_packaged_app_path_enables_native_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    executable = Path("/Applications/bt-web-report Manager.app/Contents/MacOS/bt-web-report Manager")
    monkeypatch.delenv("BTWR_MANAGER_NATIVE", raising=False)

    assert app._running_from_app_bundle(executable)
