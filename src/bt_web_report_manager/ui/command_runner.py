"""Qt process runner for streaming action output."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QProcess, Signal

from bt_web_report_manager.commands import CommandSpec


class ProcessRunner(QObject):
    started = Signal(str)
    output = Signal(str)
    finished = Signal(str, int, bool)

    def __init__(self) -> None:
        super().__init__()
        self._process: QProcess | None = None
        self._spec: CommandSpec | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None

    @property
    def current_spec(self) -> CommandSpec | None:
        return self._spec

    def start(self, spec: CommandSpec) -> bool:
        if self._process is not None:
            self.output.emit("A command is already running.")
            return False

        process = QProcess(self)
        if spec.cwd is not None:
            process.setWorkingDirectory(str(spec.cwd))
        process.setProgram(spec.args[0])
        process.setArguments(list(spec.args[1:]))
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.errorOccurred.connect(self._error)
        process.finished.connect(self._finished)
        self._process = process
        self._spec = spec
        self.started.emit(f"$ {' '.join(spec.args)}")
        process.start()
        return True

    def stop(self) -> None:
        if self._process is None:
            return
        self.output.emit("Stopping process...")
        self._process.terminate()
        if not self._process.waitForFinished(2000):
            self._process.kill()

    def _read_stdout(self) -> None:
        if self._process is None:
            return
        text = _decode_qbytearray(self._process.readAllStandardOutput())
        if text:
            self.output.emit(text.rstrip())

    def _read_stderr(self) -> None:
        if self._process is None:
            return
        text = _decode_qbytearray(self._process.readAllStandardError())
        if text:
            self.output.emit(text.rstrip())

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if self._process is None:
            return
        spec = self._spec
        name = spec.name if spec is not None else "Command"
        refresh = spec.refresh_on_success if spec is not None else False
        self.finished.emit(name, exit_code, refresh)
        self._process = None
        self._spec = None

    def _error(self, error: QProcess.ProcessError) -> None:
        spec = self._spec
        name = spec.name if spec is not None else "Command"
        message = self._process.errorString() if self._process is not None else str(error)
        self.output.emit(message)
        self.finished.emit(name, -1, False)
        self._process = None
        self._spec = None


def _decode_qbytearray(value: Any) -> str:
    raw = value.data() if hasattr(value, "data") else value
    return bytes(raw).decode(errors="replace")
