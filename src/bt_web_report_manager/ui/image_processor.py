"""Drag-and-drop PDF -> PNG modal.

Generic utility: the user drops one or more PDFs, each is rendered into
a full-resolution and a web-optimized PNG, and both are written to
``~/Desktop/bt-web-report-images/``. Not scoped to any project.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from nicegui import ui

from bt_web_report_manager.image_processing import (
    PdfConversionResult,
    convert_pdf,
    default_output_dir,
)
from bt_web_report_manager.trace import trace_event, trace_exception


async def open_image_processor_dialog() -> None:
    """Open the PDF -> PNG drag-and-drop modal."""
    output_dir = default_output_dir()
    trace_event("ui.image_processor.open", output_dir=output_dir)

    dialog = ui.dialog().props("persistent")
    log_lines: list[str] = []
    log_widget_ref: dict[str, Any] = {}

    def log(line: str) -> None:
        log_lines.append(line)
        widget = log_widget_ref.get("widget")
        if widget is not None:
            widget.push(line)

    with dialog, ui.card().classes("min-w-[560px] max-w-[760px]"):
        ui.label("PDF -> PNG").classes("dialog-title")
        ui.label(
            "Drop one or more PDFs below. Each page is rendered to a full-resolution "
            "PNG (300 DPI) and a web-optimized PNG (144 DPI, palette + optimize)."
        ).classes("text-sm").style("color: var(--text-2); line-height: 1.5;")

        ui.label(f"Output folder: {output_dir}").style(
            "font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); margin-top: 6px;"
        )

        upload = (
            ui.upload(
                multiple=True,
                auto_upload=True,
                on_upload=lambda e: asyncio.create_task(_handle_upload(e, output_dir, log)),
            )
            .props('accept=".pdf" label="Drop PDFs here or click to browse" flat bordered')
            .classes("w-full")
            .style("margin-top: 10px;")
        )
        upload.on("rejected", lambda _e: ui.notify("Only .pdf files are accepted.", type="warning"))

        log_widget = ui.log(max_lines=500).classes("nicegui-log").style(
            "margin-top: 12px; min-height: 180px; max-height: 320px; font-size: 12px;"
        )
        log_widget_ref["widget"] = log_widget
        for line in log_lines:
            log_widget.push(line)

        with ui.row().classes("w-full justify-between items-center mt-3"):
            ui.button(
                "Reveal output folder",
                icon="folder_open",
                color=None,
                on_click=lambda: _reveal_in_finder(output_dir),
            ).props("flat unelevated no-caps").classes("action-btn")
            ui.button(
                "Close",
                color=None,
                on_click=dialog.close,
            ).props("flat unelevated no-caps").classes("action-btn is-primary")

    await dialog


async def _handle_upload(event: Any, output_dir: Path, log: Any) -> None:
    name = getattr(event, "name", "uploaded.pdf")
    if not name.lower().endswith(".pdf"):
        log(f"SKIP: {name} (not a PDF)")
        trace_event("ui.image_processor.skip_non_pdf", name=name)
        return

    log(f"Processing {name}...")
    trace_event("ui.image_processor.upload_received", name=name)

    try:
        data = event.content.read()
    except Exception as exc:
        trace_exception("ui.image_processor.read_failed", exc, name=name)
        log(f"FAILED: {name}: could not read upload ({exc})")
        return

    # Write bytes to a temp file that preserves the original PDF basename so
    # convert_pdf bakes that stem into the output PNG names.
    tmp_dir = Path(tempfile.mkdtemp(prefix="btwr-pdf-"))
    staged = tmp_dir / name
    try:
        staged.write_bytes(data)
        result = await asyncio.to_thread(convert_pdf, staged, output_dir)
    finally:
        try:
            staged.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass

    _log_result(result, log)


def _log_result(result: PdfConversionResult, log: Any) -> None:
    if not result.ok:
        trace_event(
            "ui.image_processor.result_error",
            source=result.source,
            error=result.error,
            pages_written=result.page_count,
        )
        log(f"FAILED: {result.source.name}: {result.error}")
        if result.page_count:
            log(f"  (wrote {result.page_count} page(s) before the failure)")
        ui.notify(f"Failed: {result.source.name}", type="negative")
        return

    trace_event(
        "ui.image_processor.result_ok",
        source=result.source,
        page_count=result.page_count,
        full_paths=[str(p) for p in result.full_paths],
        optimized_paths=[str(p) for p in result.optimized_paths],
    )
    log(f"OK: {result.source.name}: {result.page_count} page(s)")
    for full, optimized in zip(result.full_paths, result.optimized_paths, strict=True):
        log(f"  - {full.name}  +  {optimized.name}")
    ui.notify(
        f"{result.source.name}: {result.page_count * 2} PNG(s) written",
        type="positive",
    )


def _reveal_in_finder(path: Path) -> None:
    trace_event("ui.image_processor.reveal", path=path)
    try:
        subprocess.run(["open", str(path)], check=False)
    except OSError as exc:
        trace_exception("ui.image_processor.reveal_failed", exc, path=path)
        ui.notify(f"Could not open Finder: {exc}", type="warning")
