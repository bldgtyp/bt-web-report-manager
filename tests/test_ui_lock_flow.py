"""Tests for the lock-handling flow used by mutating actions.

The actual UI integration lives in ``ui/main.py::build_page``; this file
covers the underlying ``locks.py`` flow that gets called from
``prepare_mutating_action`` (read existing lock → decide whether to prompt
→ overwrite with the current user's lock).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from bt_web_report_manager.locks import (
    current_host,
    current_user,
    is_current_user_lock,
    lock_requires_confirmation,
    lock_warning_message,
    read_lock,
    write_lock,
)


def test_other_user_lock_requires_confirmation(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    _write_other_user_lock(project)

    lock = read_lock(project)
    assert lock is not None
    assert lock.user == "john"
    assert lock_requires_confirmation(lock) is True
    assert "Continue and replace the lock?" in lock_warning_message(lock)


def test_current_user_lock_does_not_require_confirmation(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    write_lock(project, "sample", ttl_hours=4)

    lock = read_lock(project)
    assert lock is not None
    assert is_current_user_lock(lock)
    assert lock_requires_confirmation(lock) is False


def test_overwriting_lock_replaces_owner(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    _write_other_user_lock(project)

    write_lock(project, "sample", ttl_hours=4)

    lock = read_lock(project)
    assert lock is not None
    assert lock.user == current_user()
    assert lock.host == current_host()


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "Sample Project" / "04_Web"
    project.mkdir(parents=True)
    (project / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "slug": "sample",
                "project_title": "Sample Project",
                "source_files": {"data_dir": "data"},
            },
            sort_keys=False,
        )
    )
    return project


def _write_other_user_lock(project: Path) -> None:
    lock_path = project / ".bldgtyp" / "lock.yaml"
    lock_path.parent.mkdir()
    lock_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "user": "john",
                "host": "Johns-Mac.local",
                "project_slug": "sample",
                "opened_at": "2026-05-13T12:00:00+00:00",
                "updated_at": "2026-05-13T12:00:00+00:00",
                "expires_at": "2099-05-13T16:00:00+00:00",
            },
            sort_keys=False,
        )
    )
