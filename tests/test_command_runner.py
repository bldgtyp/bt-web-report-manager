import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from bt_web_report_manager.commands import CommandSpec
from bt_web_report_manager.ui.command_runner import ProcessRunner

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@dataclass
class RunnerEvents:
    started: list[str] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    finished: list[tuple[str, int, bool, bool]] = field(default_factory=list)


def test_process_runner_streams_output_and_exit_code(tmp_path: Path) -> None:
    _app()
    runner = ProcessRunner()
    events = _capture_events(runner)

    started = runner.start(CommandSpec("Echo", ("/bin/echo", "runner-ok"), cwd=tmp_path, refresh_on_success=True))

    assert started
    assert _wait_until(lambda: bool(events.finished))
    assert events.started == ["$ /bin/echo runner-ok"]
    assert events.output == ["runner-ok"]
    assert events.finished == [("Echo", 0, True, False)]
    assert not runner.is_running


def test_process_runner_stop_is_asynchronous(tmp_path: Path) -> None:
    _app()
    runner = ProcessRunner()
    events = _capture_events(runner)
    spec = CommandSpec("Sleep", ("/bin/sh", "-lc", "sleep 10"), cwd=tmp_path, long_running=True)

    assert runner.start(spec)
    assert _wait_until(lambda: runner.is_running)
    before = time.monotonic()
    runner.stop()
    elapsed = time.monotonic() - before

    assert elapsed < 0.5
    assert _wait_until(lambda: bool(events.finished), timeout_ms=4000)
    assert "Stopping process..." in events.output
    assert events.finished[-1][0] == "Sleep"
    assert events.finished[-1][2] is False
    assert events.finished[-1][3] is True
    assert not runner.is_running


def _capture_events(runner: ProcessRunner) -> RunnerEvents:
    events = RunnerEvents()
    runner.started.connect(events.started.append)
    runner.output.connect(events.output.append)
    runner.finished.connect(
        lambda name, exit_code, refresh, canceled: events.finished.append((name, exit_code, refresh, canceled))
    )
    return events


def _app() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _wait_until(predicate: Callable[[], bool], timeout_ms: int = 2000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if predicate():
            return True
        loop = QEventLoop()
        QTimer.singleShot(10, loop.quit)
        loop.exec()
    return predicate()
