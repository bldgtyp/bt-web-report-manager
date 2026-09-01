"""PDFium access must stay single-threaded.

PDFium is not thread-safe and corrupts its heap when two threads render at
once, which aborts the whole process rather than raising. These tests assert
the serialization contract with an instrumented stub, so a regression fails as
an assertion instead of killing the test run.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pytest

from bt_web_report_manager import image_processing


class ConcurrencyProbe:
    """Stand-in for ``_render_page`` that records how many callers overlap."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0
        self.peak = 0
        self.threads: set[str] = set()

    def __call__(self, page: Any, dpi: int) -> Any:
        with self._lock:
            self._active += 1
            self.peak = max(self.peak, self._active)
            self.threads.add(threading.current_thread().name)
        try:
            # Long enough that genuinely parallel callers would overlap here.
            threading.Event().wait(0.02)
            return page.render(scale=dpi / 72.0).to_pil()
        finally:
            with self._lock:
                self._active -= 1


@pytest.fixture
def one_page_pdf(tmp_path: Path) -> Path:
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(200, 200)
    target = tmp_path / "probe.pdf"
    pdf.save(str(target))
    pdf.close()
    return target


def test_convert_pdf_serializes_pdfium_across_threads(
    monkeypatch: pytest.MonkeyPatch,
    one_page_pdf: Path,
    tmp_path: Path,
) -> None:
    probe = ConcurrencyProbe()
    monkeypatch.setattr(image_processing, "_render_page", probe)
    out = tmp_path / "out"

    threads = [threading.Thread(target=image_processing.convert_pdf, args=(one_page_pdf, out)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert probe.peak == 1, f"{probe.peak} threads were inside PDFium at once"


@pytest.mark.asyncio
async def test_convert_pdf_async_queues_onto_one_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
    one_page_pdf: Path,
    tmp_path: Path,
) -> None:
    probe = ConcurrencyProbe()
    monkeypatch.setattr(image_processing, "_render_page", probe)
    out = tmp_path / "out"

    results = await asyncio.gather(*(image_processing.convert_pdf_async(one_page_pdf, out) for _ in range(4)))

    assert all(result.ok for result in results)
    assert probe.peak == 1
    assert len(probe.threads) == 1
    assert next(iter(probe.threads)).startswith("btwr-pdfium")


def test_convert_pdf_writes_a_full_and_optimized_png(one_page_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"

    result = image_processing.convert_pdf(one_page_pdf, out)

    assert result.ok
    assert result.page_count == 1
    assert result.full_paths == (out / "probe.full.png",)
    assert result.optimized_paths == (out / "probe.optimized.png",)
    assert all(path.stat().st_size > 0 for path in result.full_paths + result.optimized_paths)
