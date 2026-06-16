"""Helpers for Manager local preview actions."""

from __future__ import annotations

import re
from posixpath import join
from urllib.parse import urlparse

LOCAL_PREVIEW_URL_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:/[^\s]*)?")
LOCAL_PREVIEW_HOSTS = {"localhost", "127.0.0.1", "::1"}
TINA_API_PATHS = {"/graphql"}

REPORT_PDF_READY_MARKER = "PDF ready:"


def report_pdf_path_from_log_line(line: str) -> str | None:
    """Extract the built report.pdf path from a ``btwr build-pdf`` log line.

    ``btwr build-pdf`` ends with a ``PDF ready: <path>`` line once the artifact
    has been written; the Manager scans for it to open the PDF for QA.
    """

    index = line.find(REPORT_PDF_READY_MARKER)
    if index == -1:
        return None
    candidate = line[index + len(REPORT_PDF_READY_MARKER) :].strip()
    if not candidate.endswith("report.pdf"):
        return None
    return candidate


def local_preview_url_from_log_line(line: str) -> str | None:
    """Extract the local Astro URL from a dev-server log line."""

    match = LOCAL_PREVIEW_URL_RE.search(line)
    if match is None:
        return None
    url = match.group(0).rstrip(".,;")
    parsed = urlparse(url)
    if parsed.hostname not in LOCAL_PREVIEW_HOSTS:
        return None
    if parsed.path.rstrip("/") in TINA_API_PATHS:
        return None
    return url


def tina_admin_url(preview_url: str) -> str:
    """Return the TinaCMS admin URL for a local Astro preview URL."""

    parsed = urlparse(preview_url)
    base_path = parsed.path if parsed.path.endswith("/") else f"{parsed.path}/"
    admin_path = join(base_path, "admin/index.html")
    return parsed._replace(path=admin_path, params="", query="", fragment="").geturl()


def editor_browser_urls(preview_url: str) -> tuple[str, str]:
    """Return the TinaCMS admin URL and matching live-preview URL."""

    return (tina_admin_url(preview_url), preview_url)
