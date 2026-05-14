"""Sanity tests for the post-port packaging story (nicegui-pack)."""

from __future__ import annotations

from pathlib import Path
import tomllib

from bt_web_report_manager import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_nicegui_dependencies() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = config["project"]

    assert project["name"] == "bt-web-report-manager"
    assert project["version"] == __version__
    deps = project["dependencies"]
    assert any(d.startswith("nicegui") for d in deps), deps
    assert any(d.startswith("pywebview") for d in deps), deps
    # PySide6 / briefcase must not be present any more
    assert not any(d.startswith("PySide6") for d in deps), deps
    package_extra = project.get("optional-dependencies", {}).get("package", [])
    assert any(d.startswith("pyinstaller") for d in package_extra), package_extra
    assert not any(d.startswith("briefcase") for d in package_extra), package_extra


def test_no_briefcase_block_in_pyproject() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "briefcase" not in config.get("tool", {})


def test_packaging_assets_exist() -> None:
    assert (ROOT / "resources" / "icon.svg").is_file()
    assert (ROOT / "resources" / "icon.icns").is_file()


def test_build_script_exists() -> None:
    script = ROOT / "scripts" / "build-app.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111, "build-app.sh must be executable"


def test_build_script_stamps_bundle_version_metadata() -> None:
    script = (ROOT / "scripts" / "build-app.sh").read_text()
    assert "CFBundleIdentifier" in script
    assert 'set_plist_value "CFBundleShortVersionString" "$VERSION"' in script
    assert 'set_plist_value "CFBundleVersion" "$VERSION"' in script
    assert "verify_release_zip" in script


def test_makefile_has_release_targets() -> None:
    makefile = (ROOT / "Makefile").read_text()
    assert "release-build:" in makefile
    assert "publish-release:" in makefile
    assert "NOTARIZE_PROFILE" in makefile
    assert "CODESIGN_IDENTITY" in makefile
