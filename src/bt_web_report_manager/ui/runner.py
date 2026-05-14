"""Async subprocess runner that streams stdout/stderr to UI callbacks.

Replaces the QProcess-based ``ProcessRunner`` with an ``asyncio.subprocess``
implementation. Same public surface: ``is_running``, ``start(spec)``,
``stop()``, ``shutdown()`` and ``on_log`` / ``on_done`` callbacks that mirror
the previous UI-runner payloads.
"""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Callable
from typing import Awaitable

from bt_web_report_manager.commands import CommandSpec, executable_search_path
from bt_web_report_manager.trace import trace_event, trace_exception

LogCallback = Callable[[str], None]
DoneCallback = Callable[[str, int, bool, bool], None]
"""``(command_name, exit_code, refresh_on_success, canceled)``"""

STOP_GRACE_SECONDS = 2.0
PNPM_STOP_LIFECYCLE_MESSAGE = "[stop] pnpm reported ELIFECYCLE while stopping; treating it as expected shutdown noise."


def normalize_runner_output(line: str, *, stop_requested: bool) -> str | None:
    """Normalize noisy subprocess output before it reaches the UI log."""

    if stop_requested and "ELIFECYCLE" in line and "Command failed" in line:
        return PNPM_STOP_LIFECYCLE_MESSAGE
    return line


class ProcessRunner:
    def __init__(self, on_log: LogCallback, on_done: DoneCallback) -> None:
        self._on_log = on_log
        self._on_done = on_done
        self._process: asyncio.subprocess.Process | None = None
        self._spec: CommandSpec | None = None
        self._stop_requested = False
        self._reader_task: asyncio.Task[None] | None = None
        self._wait_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        # Treat the runner as busy until _wait_for_exit has cleared _process in
        # its finally block — otherwise a start() racing with cleanup orphans the
        # in-flight wait/reader tasks.
        return self._process is not None

    @property
    def current_spec(self) -> CommandSpec | None:
        return self._spec

    async def start(self, spec: CommandSpec) -> bool:
        if self.is_running:
            trace_event("runner.start.rejected_busy", requested=spec.name, current=self._spec)
            self._on_log("A command is already running.")
            return False

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        env["PATH"] = executable_search_path()
        trace_event(
            "runner.start",
            name=spec.name,
            args=spec.args,
            cwd=spec.cwd,
            long_running=spec.long_running,
            refresh_on_success=spec.refresh_on_success,
            path=env["PATH"],
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *spec.args,
                cwd=str(spec.cwd) if spec.cwd is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=os.name != "nt",
            )
        except (OSError, FileNotFoundError) as exc:
            trace_exception("runner.start.failed", exc, name=spec.name, args=spec.args, cwd=spec.cwd)
            self._on_log(f"Failed to start {spec.name}: {exc}")
            self._on_done(spec.name, -1, False, False)
            return False

        self._process = process
        self._spec = spec
        self._stop_requested = False
        trace_event("runner.started", name=spec.name, pid=process.pid)
        self._on_log(f"$ {' '.join(spec.args)}")
        self._reader_task = asyncio.create_task(self._stream(process))
        self._wait_task = asyncio.create_task(self._wait_for_exit())
        return True

    def stop(self) -> None:
        if not self.is_running or self._process is None:
            trace_event("runner.stop.ignored_not_running")
            return
        if self._stop_requested:
            trace_event("runner.stop.ignored_already_requested", pid=self._process.pid)
            return
        self._stop_requested = True
        trace_event("runner.stop.requested", pid=self._process.pid, spec=self._spec)
        self._on_log("Stopping process...")
        self._signal_process_tree(signal.SIGTERM)
        asyncio.create_task(self._kill_if_alive())

    async def shutdown(self) -> None:
        """Block until any running process has exited; SIGKILL after grace period."""
        if not self.is_running or self._process is None:
            trace_event("runner.shutdown.no_process")
            return
        self._stop_requested = True
        trace_event("runner.shutdown.terminating", pid=self._process.pid, spec=self._spec)
        self._signal_process_tree(signal.SIGTERM)
        try:
            await asyncio.wait_for(self._process.wait(), timeout=STOP_GRACE_SECONDS)
        except asyncio.TimeoutError:
            if self._process.returncode is None:
                trace_event("runner.shutdown.kill_after_timeout", pid=self._process.pid)
                self._signal_process_tree(signal.SIGKILL)
                await self._process.wait()
        if self._wait_task is not None:
            try:
                await self._wait_task
            except asyncio.CancelledError:
                pass

    async def _stream(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        try:
            async for raw in process.stdout:
                text = raw.decode(errors="replace").rstrip()
                if text:
                    normalized = normalize_runner_output(text, stop_requested=self._stop_requested)
                    trace_event("runner.output", spec=self._spec, line=text, normalized=normalized)
                    if normalized is not None:
                        self._on_log(normalized)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            trace_exception("runner.output_reader.error", exc, spec=self._spec)
            self._on_log(f"Output reader error: {exc}")

    async def _wait_for_exit(self) -> None:
        assert self._process is not None
        spec = self._spec
        try:
            await self._process.wait()
            if self._reader_task is not None:
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass
        finally:
            name = spec.name if spec is not None else "Command"
            refresh = spec.refresh_on_success if spec is not None else False
            canceled = self._stop_requested
            code = self._process.returncode if self._process is not None else -1
            trace_event("runner.done", name=name, returncode=code, refresh=refresh, canceled=canceled)
            self._process = None
            self._spec = None
            self._reader_task = None
            self._wait_task = None
            self._stop_requested = False
            self._on_done(name, code if code is not None else -1, refresh, canceled)

    async def _kill_if_alive(self) -> None:
        await asyncio.sleep(STOP_GRACE_SECONDS)
        if self.is_running and self._process is not None:
            self._on_log("Process did not stop after 2 seconds; killing it.")
            trace_event("runner.kill_after_grace", pid=self._process.pid, spec=self._spec)
            self._signal_process_tree(signal.SIGKILL)

    def _signal_process_tree(self, sig: signal.Signals) -> None:
        if self._process is None:
            return
        pid = self._process.pid
        if os.name != "nt":
            try:
                os.killpg(pid, sig)
                trace_event("runner.signal.process_group", pid=pid, signal=sig.name, spec=self._spec)
                return
            except ProcessLookupError:
                trace_event("runner.signal.process_group_missing", pid=pid, signal=sig.name, spec=self._spec)
                return
            except PermissionError as exc:
                trace_exception(
                    "runner.signal.process_group_permission", exc, pid=pid, signal=sig.name, spec=self._spec
                )
        try:
            if sig == signal.SIGTERM:
                self._process.terminate()
            else:
                self._process.kill()
            trace_event("runner.signal.process", pid=pid, signal=sig.name, spec=self._spec)
        except ProcessLookupError:
            trace_event("runner.signal.process_missing", pid=pid, signal=sig.name, spec=self._spec)


def schedule(coro: Awaitable[None]) -> asyncio.Task[None]:
    """Convenience helper for fire-and-forget tasks inside UI handlers."""
    return asyncio.create_task(coro)  # type: ignore[arg-type]
