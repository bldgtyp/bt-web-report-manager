import pytest

from bt_web_report_manager.updates import check_for_updates, compare_versions, latest_release


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


def test_latest_release_reports_current_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "bt_web_report_manager.updates.requests.get",
        _get_response(
            [
                {
                    "tag_name": "v0.0.1",
                    "html_url": "https://github.com/bldgtyp/bt-web-report-manager/releases/tag/v0.0.1",
                    "draft": False,
                    "prerelease": False,
                    "assets": [],
                }
            ]
        ),
    )

    release = latest_release("bldgtyp", "bt-web-report-manager", "0.0.1")

    assert release is not None
    assert not release.is_update
    assert release.asset_url is None


def test_latest_release_reports_update_and_prefers_zip_asset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "bt_web_report_manager.updates.requests.get",
        _get_response(
            [
                {
                    "tag_name": "v0.2.0",
                    "html_url": "https://github.com/bldgtyp/bt-web-report-manager/releases/tag/v0.2.0",
                    "name": "Manager v0.2.0",
                    "draft": False,
                    "prerelease": False,
                    "assets": [
                        {
                            "name": "checksums.txt",
                            "browser_download_url": "https://example.com/checksums.txt",
                        },
                        {
                            "name": "bt-web-report-manager-0.2.0.zip",
                            "browser_download_url": "https://example.com/manager.zip",
                        },
                    ],
                }
            ]
        ),
    )

    release = latest_release("bldgtyp", "bt-web-report-manager", "0.0.1")

    assert release is not None
    assert release.is_update
    assert release.name == "Manager v0.2.0"
    assert release.asset_name == "bt-web-report-manager-0.2.0.zip"
    assert release.asset_url == "https://example.com/manager.zip"


def test_latest_release_skips_prereleases_and_malformed_releases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "bt_web_report_manager.updates.requests.get",
        _get_response(
            [
                {
                    "tag_name": "v9.9.9",
                    "html_url": "https://github.com/bldgtyp/bt-web-report-manager/releases/tag/v9.9.9",
                    "draft": False,
                    "prerelease": True,
                },
                {
                    "tag_name": "nightly",
                    "html_url": "https://github.com/bldgtyp/bt-web-report-manager/releases/tag/nightly",
                    "draft": False,
                    "prerelease": False,
                },
                {
                    "tag_name": "v0.3.0",
                    "html_url": "https://github.com/bldgtyp/bt-web-report-manager/releases/tag/v0.3.0",
                    "draft": False,
                    "prerelease": False,
                },
            ]
        ),
    )

    release = latest_release("bldgtyp", "bt-web-report-manager", "0.0.1")

    assert release is not None
    assert release.version == "v0.3.0"
    assert release.is_update


def test_check_for_updates_handles_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bt_web_report_manager.updates.requests.get", _get_response({"message": "bad shape"}))

    result = check_for_updates("bldgtyp", "bt-web-report-manager", "0.0.1")

    assert not result.ok
    assert "not a list" in result.message


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


def _get_response(payload: object) -> object:
    def get(*_args: object, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(payload)

    return get
