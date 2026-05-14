from bt_web_report_manager.models import ToolStatus
from bt_web_report_manager.ui.dialogs import _can_repair_btwr


def test_can_repair_btwr_only_for_missing_btwr_with_workspace_candidate() -> None:
    missing_btwr = ToolStatus("btwr", "btwr", None, None, False, "btwr not found on PATH")

    assert _can_repair_btwr(missing_btwr, "/tmp/workspace/btwr")
    assert not _can_repair_btwr(missing_btwr, None)
    assert not _can_repair_btwr(
        ToolStatus("pnpm", "pnpm", None, None, False, "pnpm not found on PATH"),
        "/tmp/workspace/btwr",
    )
    assert not _can_repair_btwr(
        ToolStatus("btwr", "/tmp/workspace/btwr", "/tmp/workspace/btwr", "ok", True, "ok"),
        "/tmp/workspace/btwr",
    )
