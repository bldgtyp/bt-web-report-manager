import pytest

from bt_web_report_manager.updates import check_for_updates, compare_versions


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("v0.1.0", "0.0.1", 1),
        ("0.1.0", "0.1.0", 0),
        ("0.1.0", "0.2.0", -1),
    ],
)
def test_compare_versions(left: str, right: str, expected: int) -> None:
    assert compare_versions(left, right) == expected


def test_check_for_updates_handles_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("offline")

    monkeypatch.setattr("bt_web_report_manager.updates.latest_release", fail)

    result = check_for_updates("bldgtyp", "bt-web-report-manager", "0.0.1")

    assert not result.ok
    assert "offline" in result.message
