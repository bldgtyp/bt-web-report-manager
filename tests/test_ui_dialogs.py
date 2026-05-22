from bt_web_report_manager.models import ManagerSettings, ToolStatus
from bt_web_report_manager.ui.dialogs import _can_repair_btwr, _partner_setup_markdown
from bt_web_report_manager.ui.project_variables import _VariableRowState, _group_rows_by_yaml_parent
from bt_web_report_manager.ui.state import ManagerState


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


def test_partner_setup_markdown_names_required_steps() -> None:
    markdown = _partner_setup_markdown(ManagerState(settings=ManagerSettings()))

    assert "Install the Manager app" in markdown
    assert "Confirm Dropbox project access" in markdown
    assert "gh auth login" in markdown
    assert "Provide a `btwr` CLI executable" in markdown
    assert "Run System Check" in markdown


def test_project_variable_rows_group_by_yaml_parent() -> None:
    groups = _group_rows_by_yaml_parent(
        [
            _VariableRowState("narrative.certification.target", ""),
            _VariableRowState("narrative.climate.weather_station_name", ""),
            _VariableRowState("narrative.mechanical.erv.type_name", ""),
            _VariableRowState("narrative.custom_note", ""),
        ]
    )

    assert [(group.label, group.path) for group in groups] == [
        ("Certification", "narrative.certification"),
        ("Climate", "narrative.climate"),
        ("Mechanical / ERV", "narrative.mechanical.erv"),
        ("Narrative", "narrative"),
    ]
    assert [index for index, _row in groups[2].rows] == [2]
