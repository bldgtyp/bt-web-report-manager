"""Tests for local preview UI helpers."""

from __future__ import annotations

from bt_web_report_manager.ui.preview import (
    editor_browser_urls,
    local_preview_url_from_log_line,
    report_pdf_path_from_log_line,
    tina_admin_url,
)


def test_local_preview_url_from_astro_log_line() -> None:
    assert local_preview_url_from_log_line("┃ Local    http://localhost:4321/") == "http://localhost:4321/"


def test_local_preview_url_accepts_loopback_variants() -> None:
    assert local_preview_url_from_log_line("ready at http://127.0.0.1:4322/report") == "http://127.0.0.1:4322/report"
    assert local_preview_url_from_log_line("ready at http://[::1]:4321/") == "http://[::1]:4321/"


def test_local_preview_url_ignores_non_local_urls() -> None:
    assert local_preview_url_from_log_line("Network http://192.168.1.10:4321/") is None
    assert local_preview_url_from_log_line("no url here") is None


def test_local_preview_url_ignores_tina_graphql_api_url() -> None:
    assert local_preview_url_from_log_line("API url: http://localhost:4001/graphql") is None


def test_tina_admin_url_uses_local_preview_origin() -> None:
    assert tina_admin_url("http://127.0.0.1:4321/") == "http://127.0.0.1:4321/admin/index.html"


def test_tina_admin_url_preserves_nested_base_path() -> None:
    assert tina_admin_url("http://localhost:4321/report/") == "http://localhost:4321/report/admin/index.html"


def test_editor_browser_urls_include_admin_and_live_preview() -> None:
    assert editor_browser_urls("http://localhost:4321/") == (
        "http://localhost:4321/admin/index.html",
        "http://localhost:4321/",
    )


def test_report_pdf_path_from_build_pdf_marker_line() -> None:
    line = "PDF ready: /Users/em/.builds/builds/project-2610/dist/report.pdf"
    assert report_pdf_path_from_log_line(line) == "/Users/em/.builds/builds/project-2610/dist/report.pdf"


def test_report_pdf_path_ignores_other_pdf_log_lines() -> None:
    # build-pdf.mjs prints its own progress lines; only the btwr marker counts.
    assert report_pdf_path_from_log_line("[build-pdf] wrote /tmp/dist/report.pdf") is None
    assert report_pdf_path_from_log_line("PDF ready: /tmp/dist/something-else.txt") is None
    assert report_pdf_path_from_log_line("navigating to http://127.0.0.1:5050/print/") is None
