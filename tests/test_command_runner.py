"""Async tests for ``ProcessRunner``."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from bt_web_report_manager.commands import CommandSpec
from bt_web_report_manager.ui.runner import ProcessRunner


@dataclass
class RunnerEvents:
    log: list[str] = field(default_factory=list)
    done: list[tuple[str, int, bool, bool]] = field(default_factory=list)
    finished: asyncio.Event = field(default_factory=asyncio.Event)


def _make_runner() -> tuple[ProcessRunner, RunnerEvents]:
    events = RunnerEvents()

    def on_done(name: str, exit_code: int, refresh: bool, canceled: bool) -> None:
        events.done.append((name, exit_code, refresh, canceled))
        events.finished.set()

    runner = ProcessRunner(on_log=events.log.append, on_done=on_done)
    return runner, events


@pytest.mark.asyncio
async def test_process_runner_streams_output_and_exit_code(tmp_path: Path) -> None:
    runner, events = _make_runner()

    started = await runner.start(CommandSpec("Echo", ("/bin/echo", "runner-ok"), cwd=tmp_path, refresh_on_success=True))

    assert started
    await asyncio.wait_for(events.finished.wait(), 5)
    assert events.log[0] == "$ /bin/echo runner-ok"
    assert "runner-ok" in events.log
    assert events.done == [("Echo", 0, True, False)]
    assert not runner.is_running


@pytest.mark.asyncio
async def test_process_runner_stop_is_asynchronous(tmp_path: Path) -> None:
    runner, events = _make_runner()
    spec = CommandSpec("Sleep", ("/bin/sh", "-lc", "sleep 10"), cwd=tmp_path, long_running=True)

    assert await runner.start(spec)
    assert runner.is_running

    runner.stop()
    await asyncio.wait_for(events.finished.wait(), 5)

    assert any("Stopping process" in line for line in events.log)
    name, _exit_code, refresh, canceled = events.done[-1]
    assert name == "Sleep"
    assert refresh is False
    assert canceled is True
    assert not runner.is_running


@pytest.mark.asyncio
async def test_process_runner_stop_terminates_child_processes(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("process-group cleanup is POSIX-specific")
    runner, events = _make_runner()
    pid_file = tmp_path / "child.pid"
    spec = CommandSpec(
        "Tree",
        ("/bin/sh", "-lc", f"sleep 30 & echo $! > {pid_file}; wait"),
        cwd=tmp_path,
        long_running=True,
    )

    assert await runner.start(spec)
    for _ in range(20):
        if pid_file.exists():
            break
        await asyncio.sleep(0.05)
    assert pid_file.exists()
    child_pid = int(pid_file.read_text().strip())

    runner.stop()
    await asyncio.wait_for(events.finished.wait(), 5)

    assert events.done[-1][3] is True
    assert not _pid_is_alive(child_pid)


@pytest.mark.asyncio
async def test_process_runner_rejects_second_start(tmp_path: Path) -> None:
    runner, events = _make_runner()
    spec = CommandSpec("Sleep", ("/bin/sh", "-lc", "sleep 5"), cwd=tmp_path, long_running=True)

    assert await runner.start(spec)

    second = await runner.start(CommandSpec("Echo", ("/bin/echo", "skipped"), cwd=tmp_path))
    assert second is False
    assert any("already running" in line for line in events.log)

    await runner.shutdown()
    assert not runner.is_running


@pytest.mark.asyncio
async def test_process_runner_missing_executable(tmp_path: Path) -> None:
    runner, events = _make_runner()

    started = await runner.start(CommandSpec("Bogus", ("/this/does/not/exist", "--help"), cwd=tmp_path))

    assert started is False
    assert any("Failed to start Bogus" in line for line in events.log)
    assert events.done == [("Bogus", -1, False, False)]


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
