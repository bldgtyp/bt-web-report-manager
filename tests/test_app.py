from __future__ import annotations

from pathlib import Path

import pytest
from nicegui import app as nicegui_app

from bt_web_report_manager import app
from bt_web_report_manager.ui.theme import CSS
from bt_web_report_manager.ui.main import _hidden_project_paths_with, _project_paths_without


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


def test_show_browser_override_disables_auto_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BTWR_MANAGER_SHOW", "0")

    assert not app._show_browser_enabled()


def test_native_window_enables_text_selection() -> None:
    nicegui_app.native.window_args.pop("text_select", None)

    app._configure_native_window(native=True)

    assert nicegui_app.native.window_args["text_select"] is True


def test_browser_mode_does_not_touch_native_window_args() -> None:
    nicegui_app.native.window_args.pop("text_select", None)

    app._configure_native_window(native=False)

    assert "text_select" not in nicegui_app.native.window_args


def test_global_css_keeps_visible_text_selectable() -> None:
    assert "-webkit-user-select: text !important;" in CSS
    assert "user-select: text !important;" in CSS
    assert ".screen-root.is-frozen" in CSS
    assert ".screen-root.is-frozen" in CSS[CSS.index("user-select: text !important;") :]


def test_hidden_project_paths_with_appends_resolved_path_once(tmp_path: Path) -> None:
    project = tmp_path / "Project" / "04_Web"
    project.mkdir(parents=True)

    hidden = _hidden_project_paths_with((), project)
    assert hidden == (project.resolve(),)

    assert _hidden_project_paths_with(hidden, project) == hidden


def test_project_paths_without_removes_matching_resolved_path(tmp_path: Path) -> None:
    project = tmp_path / "Project" / "04_Web"
    other = tmp_path / "Other" / "04_Web"
    project.mkdir(parents=True)
    other.mkdir(parents=True)

    assert _project_paths_without((project, other), project.resolve()) == (other,)
