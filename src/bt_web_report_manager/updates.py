"""GitHub Releases update check."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests

SEMVER_RE = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+].*)?$")


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    url: str
    name: str | None
    body: str | None
    is_update: bool


@dataclass(frozen=True)
class UpdateCheckResult:
    ok: bool
    message: str
    release: ReleaseInfo | None = None


def latest_release(owner: str, repo: str, current_version: str, timeout: float = 5) -> ReleaseInfo | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    releases = response.json()
    if not isinstance(releases, list):
        raise ValueError("GitHub releases response is not a list")
    for raw in releases:
        if not isinstance(raw, dict) or raw.get("draft") or raw.get("prerelease"):
            continue
        tag = raw.get("tag_name")
        html_url = raw.get("html_url")
        if not isinstance(tag, str) or not isinstance(html_url, str):
            continue
        return ReleaseInfo(
            version=tag,
            url=html_url,
            name=_optional_str(raw.get("name")),
            body=_optional_str(raw.get("body")),
            is_update=compare_versions(tag, current_version) > 0,
        )
    return None


def check_for_updates(owner: str, repo: str, current_version: str, timeout: float = 5) -> UpdateCheckResult:
    try:
        release = latest_release(owner, repo, current_version, timeout=timeout)
    except Exception as exc:
        return UpdateCheckResult(False, f"Update check failed: {exc}")
    if release is None:
        return UpdateCheckResult(True, "No GitHub Releases found.")
    if release.is_update:
        return UpdateCheckResult(True, f"Update available: {release.version}", release)
    return UpdateCheckResult(True, f"Current version is up to date ({current_version}).", release)


def compare_versions(left: str, right: str) -> int:
    left_parts = _version_tuple(left)
    right_parts = _version_tuple(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(value)
    if not match:
        raise ValueError(f"not a semantic version: {value}")
    return (int(match.group("major")), int(match.group("minor")), int(match.group("patch")))


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None
