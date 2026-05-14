from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from bt_web_report_manager.update_installer import (
    APP_BUNDLE_NAME,
    UpdateInstallError,
    _find_app_bundle,
    _safe_extract_zip,
    current_app_bundle,
    is_installable_asset,
)


def test_is_installable_asset_only_accepts_zip() -> None:
    assert is_installable_asset("bt-web-report-manager-0.0.3.zip")
    assert is_installable_asset("BT-WEB-REPORT-MANAGER-0.0.3.ZIP")
    assert not is_installable_asset("bt-web-report-manager-0.0.3.dmg")
    assert not is_installable_asset(None)


def test_current_app_bundle_finds_packaged_executable() -> None:
    executable = Path("/Applications") / APP_BUNDLE_NAME / "Contents" / "MacOS" / "bt-web-report Manager"

    assert current_app_bundle(executable) == Path("/Applications") / APP_BUNDLE_NAME


def test_safe_extract_zip_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../escape.txt", "bad")

    with pytest.raises(UpdateInstallError, match="unsafe path"):
        _safe_extract_zip(archive, tmp_path / "out")


def test_safe_extract_zip_uses_macos_archive_extraction(tmp_path: Path) -> None:
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("payload/file.txt", "ok")

    _safe_extract_zip(archive, tmp_path / "out")

    assert (tmp_path / "out" / "payload" / "file.txt").read_text() == "ok"


def test_find_app_bundle_prefers_expected_name(tmp_path: Path) -> None:
    app = tmp_path / APP_BUNDLE_NAME
    (app / "Contents" / "MacOS").mkdir(parents=True)

    assert _find_app_bundle(tmp_path) == app


def test_find_app_bundle_rejects_ambiguous_archive(tmp_path: Path) -> None:
    for name in ("A.app", "B.app"):
        (tmp_path / name / "Contents" / "MacOS").mkdir(parents=True)

    with pytest.raises(UpdateInstallError, match="multiple"):
        _find_app_bundle(tmp_path)
