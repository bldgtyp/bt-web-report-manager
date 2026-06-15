from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bt_web_report_manager.image_processing import PdfConversionResult
from bt_web_report_manager.ui import image_processor


class AsyncUpload:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    async def read(self) -> bytes:
        return self._data


@pytest.mark.asyncio
async def test_read_upload_bytes_supports_current_nicegui_file_event() -> None:
    event = SimpleNamespace(file=AsyncUpload("hero-full.pdf", b"pdf-bytes"))

    assert image_processor._upload_name(event) == "hero-full.pdf"
    assert await image_processor._read_upload_bytes(event) == b"pdf-bytes"


@pytest.mark.asyncio
async def test_read_upload_bytes_supports_legacy_content_event() -> None:
    event = SimpleNamespace(name="legacy.pdf", content=BytesIO(b"legacy-pdf-bytes"))

    assert image_processor._upload_name(event) == "legacy.pdf"
    assert await image_processor._read_upload_bytes(event) == b"legacy-pdf-bytes"


@pytest.mark.asyncio
async def test_handle_upload_stages_current_nicegui_file_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    event = SimpleNamespace(file=AsyncUpload("nested/hero-full.pdf", b"staged-pdf"))
    logs: list[str] = []
    seen: dict[str, Any] = {}

    def fake_convert_pdf(pdf_path: Path, output_dir: Path) -> PdfConversionResult:
        seen["pdf_name"] = pdf_path.name
        seen["pdf_data"] = pdf_path.read_bytes()
        seen["output_dir"] = output_dir
        return PdfConversionResult(source=pdf_path)

    def fake_log_result(result: PdfConversionResult, log: Any) -> None:
        log(f"OK: {result.source.name}")

    monkeypatch.setattr(image_processor, "convert_pdf", fake_convert_pdf)
    monkeypatch.setattr(image_processor, "_log_result", fake_log_result)

    await image_processor._handle_upload(event, tmp_path, logs.append)

    assert logs == ["Processing hero-full.pdf...", "OK: hero-full.pdf"]
    assert seen == {
        "pdf_name": "hero-full.pdf",
        "pdf_data": b"staged-pdf",
        "output_dir": tmp_path,
    }
