"""Async subprocess runner that streams stdout/stderr to UI callbacks.

Replaces the QProcess-based ``ProcessRunner`` with an ``asyncio.subprocess``
implementation. Same public surface: ``is_running``, ``start(spec)``,
``stop()``, ``shutdown()`` and ``on_log`` / ``on_done`` callbacks that mirror
the old Qt signal payloads.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Awaitable

from bt_web_report_manager.commands import CommandSpec

LogCallback = Callable[[str], None]
DoneCallback = Callable[[str, int, bool, bool], None]
"""``(command_name, exit_code, refresh_on_success, canceled)``"""

STOP_GRACE_SECONDS = 2.0


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
            self._on_log("A command is already running.")
            return False

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        try:
            process = await asyncio.create_subprocess_exec(
                *spec.args,
                cwd=str(spec.cwd) if spec.cwd is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        except (OSError, FileNotFoundError) as exc:
            self._on_log(f"Failed to start {spec.name}: {exc}")
            self._on_done(spec.name, -1, False, False)
            return False

        self._process = process
        self._spec = spec
        self._stop_requested = False
        self._on_log(f"$ {' '.join(spec.args)}")
        self._reader_task = asyncio.create_task(self._stream(process))
        self._wait_task = asyncio.create_task(self._wait_for_exit())
        return True

    def stop(self) -> None:
        if not self.is_running or self._process is None:
            return
        if self._stop_requested:
            return
        self._stop_requested = True
        self._on_log("Stopping process...")
        try:
            self._process.terminate()
        except ProcessLookupError:
            return
        asyncio.create_task(self._kill_if_alive())

    async def shutdown(self) -> None:
        """Block until any running process has exited; SIGKILL after grace period."""
        if not self.is_running or self._process is None:
            return
        self._stop_requested = True
        try:
            self._process.terminate()
        except ProcessLookupError:
            pass
        else:
            try:
                await asyncio.wait_for(self._process.wait(), timeout=STOP_GRACE_SECONDS)
            except asyncio.TimeoutError:
                if self._process.returncode is None:
                    self._process.kill()
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
                    self._on_log(text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
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
            try:
                self._process.kill()
            except ProcessLookupError:
                pass


def schedule(coro: Awaitable[None]) -> asyncio.Task[None]:
    """Convenience helper for fire-and-forget tasks inside UI handlers."""
    return asyncio.create_task(coro)  # type: ignore[arg-type]
