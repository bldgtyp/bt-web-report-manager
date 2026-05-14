"""Tests for local preview UI helpers."""

from __future__ import annotations

from bt_web_report_manager.ui.preview import local_preview_url_from_log_line


def test_local_preview_url_from_astro_log_line() -> None:
    assert local_preview_url_from_log_line("┃ Local    http://localhost:4321/") == "http://localhost:4321/"


def test_local_preview_url_accepts_loopback_variants() -> None:
    assert local_preview_url_from_log_line("ready at http://127.0.0.1:4322/report") == "http://127.0.0.1:4322/report"
    assert local_preview_url_from_log_line("ready at http://[::1]:4321/") == "http://[::1]:4321/"


def test_local_preview_url_ignores_non_local_urls() -> None:
    assert local_preview_url_from_log_line("Network http://192.168.1.10:4321/") is None
    assert local_preview_url_from_log_line("no url here") is None
