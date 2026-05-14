"""Helpers for Manager local preview actions."""

from __future__ import annotations

import re
from posixpath import join
from urllib.parse import urlparse

LOCAL_PREVIEW_URL_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:/[^\s]*)?")
LOCAL_PREVIEW_HOSTS = {"localhost", "127.0.0.1", "::1"}


def local_preview_url_from_log_line(line: str) -> str | None:
    """Extract the local Astro URL from a dev-server log line."""

    match = LOCAL_PREVIEW_URL_RE.search(line)
    if match is None:
        return None
    url = match.group(0).rstrip(".,;")
    parsed = urlparse(url)
    if parsed.hostname not in LOCAL_PREVIEW_HOSTS:
        return None
    return url


def tina_admin_url(preview_url: str) -> str:
    """Return the TinaCMS admin URL for a local Astro preview URL."""

    parsed = urlparse(preview_url)
    base_path = parsed.path if parsed.path.endswith("/") else f"{parsed.path}/"
    admin_path = join(base_path, "admin/index.html")
    return parsed._replace(path=admin_path, params="", query="", fragment="").geturl()
