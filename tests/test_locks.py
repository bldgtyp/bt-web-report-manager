from datetime import datetime, timedelta, timezone
from pathlib import Path

from bt_web_report_manager.locks import lock_requires_confirmation, read_lock, refresh_lock, release_lock, write_lock
from bt_web_report_manager.models import LockInfo


def test_lock_write_refresh_release(tmp_path: Path) -> None:
    project = tmp_path / "04_Web"
    project.mkdir()
    now = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)

    created = write_lock(project, "project", ttl_hours=4, now=now)

    loaded = read_lock(project)
    assert loaded is not None
    assert loaded.project_slug == "project"
    assert loaded.expires_at == now + timedelta(hours=4)

    refreshed = refresh_lock(project, ttl_hours=2, now=now + timedelta(hours=1))
    assert refreshed is not None
    assert refreshed.expires_at == now + timedelta(hours=3)
    assert created.opened_at == refreshed.opened_at

    release_lock(project)
    assert read_lock(project) is None


def test_malformed_lock_is_reported(tmp_path: Path) -> None:
    project = tmp_path / "04_Web"
    lock_dir = project / ".bldgtyp"
    lock_dir.mkdir(parents=True)
    (lock_dir / "lock.yaml").write_text(": bad: yaml:")

    loaded = read_lock(project)

    assert loaded is not None
    assert loaded.malformed


def test_lock_requires_confirmation_for_other_unexpired_lock(tmp_path: Path) -> None:
    now = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    lock = LockInfo(
        path=tmp_path / "lock.yaml",
        user="john",
        host="Johns-Mac.local",
        expires_at=now + timedelta(hours=1),
    )

    assert lock_requires_confirmation(lock, now=now)


def test_lock_does_not_require_confirmation_when_expired(tmp_path: Path) -> None:
    now = datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)
    lock = LockInfo(
        path=tmp_path / "lock.yaml",
        user="john",
        host="Johns-Mac.local",
        expires_at=now - timedelta(minutes=1),
    )

    assert not lock_requires_confirmation(lock, now=now)
