"""Convert PDFs to PNG pairs (full-res + web-optimized).

Generic utility — not tied to a project. Output is written to
``~/Desktop/bt-web-report-images/`` (created if missing). Each input PDF
produces one pair of PNGs per page:

- Single-page PDFs: ``<stem>.full.png`` and ``<stem>.optimized.png``.
- Multi-page PDFs: ``<stem>-page<N>.full.png`` and ``<stem>-page<N>.optimized.png``.

``full`` renders at 300 DPI (print-quality). ``optimized`` renders at
144 DPI (~2x retina) and is re-saved through Pillow with ``optimize=True``
plus an 8-bit palette quantization for smaller web payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from PIL import Image

FULL_DPI = 300
OPTIMIZED_DPI = 144
DEFAULT_OUTPUT_DIRNAME = "bt-web-report-images"


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

    Existing output files with the same name are overwritten.
    """
    pdf_path = pdf_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

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


def _render_page(page: Any, dpi: int) -> Image.Image:
    scale = dpi / 72.0
    bitmap = page.render(scale=scale)
    image: Image.Image = bitmap.to_pil()
    return image
