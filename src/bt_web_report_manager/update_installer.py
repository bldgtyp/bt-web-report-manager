"""Download, verify, and install Manager app updates."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

APP_BUNDLE_NAME = "bt-web-report Manager.app"
DEVELOPER_TEAM_ID = "JPJ3AJ5U8A"


class UpdateInstallError(RuntimeError):
    """Raised when an update cannot be prepared or installed."""


@dataclass(frozen=True)
class PreparedUpdate:
    archive_path: Path
    extracted_app: Path
    temp_dir: Path


def is_installable_asset(asset_name: str | None) -> bool:
    return bool(asset_name and asset_name.lower().endswith(".zip"))


def current_app_bundle(executable: Path | None = None) -> Path | None:
    probe = (executable or Path(sys.executable)).resolve()
    candidates = [probe, *probe.parents]
    for candidate in candidates:
        if candidate.suffix == ".app" and (candidate / "Contents" / "MacOS").is_dir():
            return candidate
    return None


def prepare_update(asset_url: str, *, timeout: float = 60) -> PreparedUpdate:
    temp_dir = Path(tempfile.mkdtemp(prefix="btwr-manager-update-"))
    archive_path = temp_dir / "update.zip"
    extract_dir = temp_dir / "extracted"
    try:
        _download_file(asset_url, archive_path, timeout=timeout)
        _safe_extract_zip(archive_path, extract_dir)
        extracted_app = _find_app_bundle(extract_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return PreparedUpdate(archive_path=archive_path, extracted_app=extracted_app, temp_dir=temp_dir)


def verify_update_app(app_path: Path, *, expected_team_id: str = DEVELOPER_TEAM_ID) -> None:
    if not app_path.is_dir():
        raise UpdateInstallError(f"Update app does not exist: {app_path}")

    verify = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(app_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        raise UpdateInstallError(f"Update app code signature is invalid: {verify.stderr.strip()}")

    details = subprocess.run(
        ["codesign", "-dvvv", str(app_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if details.returncode != 0:
        raise UpdateInstallError(f"Could not inspect update app signature: {details.stderr.strip()}")
    if f"TeamIdentifier={expected_team_id}" not in details.stderr:
        raise UpdateInstallError(f"Update app was not signed by expected team {expected_team_id}.")

    gatekeeper = subprocess.run(
        ["spctl", "-a", "-vv", str(app_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if gatekeeper.returncode != 0:
        message = (gatekeeper.stderr or gatekeeper.stdout).strip()
        raise UpdateInstallError(f"Update app was not accepted by Gatekeeper: {message}")


def launch_swap_helper(
    current_app: Path,
    new_app: Path,
    *,
    current_pid: int | None = None,
    cleanup_dir: Path | None = None,
) -> Path:
    if not current_app.is_dir():
        raise UpdateInstallError(f"Current app bundle does not exist: {current_app}")
    if not new_app.is_dir():
        raise UpdateInstallError(f"Prepared update app bundle does not exist: {new_app}")

    helper_dir = Path(tempfile.mkdtemp(prefix="btwr-manager-install-"))
    helper_path = helper_dir / "install-update.zsh"
    log_path = helper_dir / "install-update.log"
    helper_path.write_text(_helper_script())
    helper_path.chmod(helper_path.stat().st_mode | stat.S_IXUSR)

    subprocess.Popen(
        [
            "/bin/zsh",
            str(helper_path),
            str(current_pid or os.getpid()),
            str(current_app),
            str(new_app),
            str(helper_dir),
            str(log_path),
            str(cleanup_dir or ""),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return helper_path


def _download_file(url: str, target: Path, *, timeout: float) -> None:
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def _safe_extract_zip(archive_path: Path, target_dir: Path) -> None:
    target_root = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                destination = (target_dir / member.filename).resolve()
                try:
                    destination.relative_to(target_root)
                except ValueError as exc:
                    raise UpdateInstallError(f"Update archive contains unsafe path: {member.filename}") from exc
            archive.extractall(target_dir)
    except zipfile.BadZipFile as exc:
        raise UpdateInstallError("Update asset is not a valid ZIP archive.") from exc


def _find_app_bundle(root: Path) -> Path:
    preferred = root / APP_BUNDLE_NAME
    if preferred.is_dir():
        return preferred
    matches = sorted(path for path in root.rglob("*.app") if (path / "Contents" / "MacOS").is_dir())
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise UpdateInstallError("Update archive did not contain a macOS .app bundle.")
    raise UpdateInstallError("Update archive contained multiple .app bundles.")


def _helper_script() -> str:
    return """#!/bin/zsh
set -euo pipefail

PID="$1"
CURRENT_APP="$2"
NEW_APP="$3"
HELPER_DIR="$4"
LOG_PATH="$5"
PAYLOAD_DIR="$6"
BACKUP_APP="${CURRENT_APP}.previous-update"

exec >>"$LOG_PATH" 2>&1
echo "Waiting for Manager process $PID to exit..."
while kill -0 "$PID" >/dev/null 2>&1; do
  sleep 0.2
done

echo "Installing update..."
rm -rf "$BACKUP_APP"
if [ -d "$CURRENT_APP" ]; then
  mv "$CURRENT_APP" "$BACKUP_APP"
fi

if ditto "$NEW_APP" "$CURRENT_APP"; then
  open "$CURRENT_APP"
  rm -rf "$BACKUP_APP"
  if [ -n "$PAYLOAD_DIR" ]; then
    rm -rf "$PAYLOAD_DIR"
  fi
  rm -rf "$HELPER_DIR"
else
  echo "Install failed; restoring previous app."
  rm -rf "$CURRENT_APP"
  if [ -d "$BACKUP_APP" ]; then
    mv "$BACKUP_APP" "$CURRENT_APP"
    open "$CURRENT_APP" || true
  fi
  osascript -e 'display dialog "bt-web-report Manager update failed. The previous app was restored." buttons {"OK"} default button "OK"' || true
  exit 1
fi
"""
