from __future__ import annotations

from pathlib import Path
import tomllib

from bt_web_report_manager import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_briefcase_config_declares_macos_dmg_app() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    briefcase = config["tool"]["briefcase"]
    app = briefcase["app"]["bt_web_report_manager"]

    assert briefcase["project_name"] == "bt-web-report-manager"
    assert briefcase["bundle"] == "com.bldgtyp"
    assert briefcase["version"] == __version__
    assert app["formal_name"] == "bt-web-report Manager"
    assert app["sources"] == ["src/bt_web_report_manager"]
    assert app["icon"] == "resources/icon"
    assert "PySide6>=6.6" in app["requires"]
    assert app["macOS"]["min_os_version"] == "12.0"
    assert app["macOS"]["dmg"]["volume_name"] == "bt-web-report Manager"


def test_packaging_assets_and_release_checklist_exist() -> None:
    assert (ROOT / "resources" / "icon.svg").is_file()
    assert (ROOT / "resources" / "icon.icns").is_file()
    checklist = (ROOT / "docs" / "release-checklist.md").read_text()
    assert "briefcase package macOS app -p dmg" in checklist
    assert "Do not add a GitHub Actions release workflow" in checklist
    assert "bt-web-report-manager-<version>.dmg" in checklist
