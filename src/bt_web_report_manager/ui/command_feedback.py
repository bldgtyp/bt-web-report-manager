"""Readable command-result text for modal feedback."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScrapeRunFeedback:
    project_title: str
    project_slug: str
    project_path: Path
    data_dir: Path
    args: tuple[str, ...]
    cwd: Path | None
    output_lines: list[str] = field(default_factory=list)

    @property
    def command(self) -> str:
        return shlex.join(self.args)

    @property
    def cwd_label(self) -> str:
        return str(self.cwd) if self.cwd is not None else "-"

    @property
    def output_text(self) -> str:
        return "\n".join(self.output_lines).strip()


def scrape_success_summary(feedback: ScrapeRunFeedback) -> str:
    return (
        "Scrape completed successfully.\n\n"
        f"Files written to:\n{feedback.data_dir}\n\n"
        f"Project: {feedback.project_title} ({feedback.project_slug})\n"
        f"Project folder: {feedback.project_path}\n"
        f"Command: {feedback.command}\n"
        f"Working directory: {feedback.cwd_label}"
    )


def scrape_error_summary(feedback: ScrapeRunFeedback, *, exit_code: int, canceled: bool) -> str:
    status = "Scrape was stopped before completion." if canceled else "Scrape failed."
    output = feedback.output_text or "No output was captured before the command ended."
    return (
        f"{status}\n\n"
        f"Exit code: {exit_code}\n"
        f"Project: {feedback.project_title} ({feedback.project_slug})\n"
        f"Project folder: {feedback.project_path}\n"
        f"Expected output folder: {feedback.data_dir}\n"
        f"Command: {feedback.command}\n"
        f"Working directory: {feedback.cwd_label}\n\n"
        f"Full command output:\n{output}"
    )
