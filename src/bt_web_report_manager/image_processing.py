"""Convert PDFs to PNG pairs (full-res + web-optimized).

Generic utility — not tied to a project. Output is written to
``~/Desktop/bt-web-report-images/`` (created if missing). Each input PDF
produces one pair of PNGs per page:

- Single-page PDFs: ``<stem>.full.png`` and ``<stem>.optimized.png``.
- Multi-page PDFs: ``<stem>-page<N>.full.png`` and ``<stem>-page<N>.optimized.png``.

``full`` renders at 300 DPI (print-quality). ``optimized`` renders at
144 DPI (~2x retina) and is re-saved through Pillow with ``optimize=True``
plus an 8-bit palette quantization for smaller web payloads.

**PDFium is not thread-safe** (upstream: "PDFium is inherently not
thread-safe"), and its global state is shared across ``PdfDocument``
instances, so two threads rendering two unrelated PDFs still corrupt each
other's heap and abort the process. This module owns that invariant rather
than leaving it to callers: every entry into PDFium goes through
``_PDFIUM_LOCK``, and ``convert_pdf_async`` schedules onto a dedicated
single-worker executor so a batch of files queues instead of piling blocked
threads into asyncio's shared default executor.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from PIL import Image

FULL_DPI = 300
OPTIMIZED_DPI = 144
DEFAULT_OUTPUT_DIRNAME = "bt-web-report-images"

# Serializes every call into PDFium. Held for the whole of ``convert_pdf`` so
# document parsing and page rasterization are both covered.
_PDFIUM_LOCK = threading.Lock()

# One long-lived worker, so PDFium is always driven from the same thread and a
# multi-file batch queues rather than fanning out.
_PDFIUM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="btwr-pdfium")


@dataclass(frozen=True)
class PdfConversionResult:
    """Outcome of converting one PDF file."""

    source: Path
    full_paths: tuple[Path, ...] = field(default_factory=tuple)
    optimized_paths: tuple[Path, ...] = field(default_factory=tuple)
    page_count: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def default_output_dir() -> Path:
    """Return ``~/Desktop/bt-web-report-images``, creating it if missing."""
    out = Path.home() / "Desktop" / DEFAULT_OUTPUT_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def convert_pdf(pdf_path: Path, output_dir: Path) -> PdfConversionResult:
    """Render ``pdf_path`` into a full + optimized PNG pair per page.

    Existing output files with the same name are overwritten. Blocks until any
    other in-flight conversion releases PDFium; see the module docstring.
    """
    pdf_path = pdf_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with _PDFIUM_LOCK:
        try:
            pdf = pdfium.PdfDocument(str(pdf_path))
        except Exception as exc:
            return PdfConversionResult(source=pdf_path, error=f"Failed to open PDF: {exc}")

        full_paths: list[Path] = []
        optimized_paths: list[Path] = []
        try:
            page_count = len(pdf)
            for index in range(page_count):
                page = pdf[index]
                page_suffix = "" if page_count == 1 else f"-page{index + 1}"
                stem = f"{pdf_path.stem}{page_suffix}"

                full_image = _render_page(page, FULL_DPI)
                full_target = output_dir / f"{stem}.full.png"
                full_image.save(full_target, format="PNG")
                full_paths.append(full_target)

                optimized_image = _render_page(page, OPTIMIZED_DPI)
                optimized_target = output_dir / f"{stem}.optimized.png"
                optimized_image.convert("P", palette=Image.Palette.ADAPTIVE).save(
                    optimized_target, format="PNG", optimize=True
                )
                optimized_paths.append(optimized_target)
        except Exception as exc:
            return PdfConversionResult(
                source=pdf_path,
                full_paths=tuple(full_paths),
                optimized_paths=tuple(optimized_paths),
                page_count=len(full_paths),
                error=f"Failed during render: {exc}",
            )
        finally:
            pdf.close()

        return PdfConversionResult(
            source=pdf_path,
            full_paths=tuple(full_paths),
            optimized_paths=tuple(optimized_paths),
            page_count=len(full_paths),
        )


async def convert_pdf_async(pdf_path: Path, output_dir: Path) -> PdfConversionResult:
    """Await :func:`convert_pdf` on the dedicated PDFium worker thread.

    Concurrent callers queue behind each other, which is what keeps a
    multi-file drop from putting several threads inside PDFium at once.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_PDFIUM_EXECUTOR, convert_pdf, pdf_path, output_dir)


def _render_page(page: Any, dpi: int) -> Image.Image:
    scale = dpi / 72.0
    bitmap = page.render(scale=scale)
    image: Image.Image = bitmap.to_pil()
    return image
