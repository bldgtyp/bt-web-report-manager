"""Project variable editor dialog."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nicegui import ui

from bt_web_report_manager.models import ProjectStatus
from bt_web_report_manager.project_variables import (
    normalize_project_variables,
    read_project_variables,
    write_project_variables,
)
from bt_web_report_manager.trace import trace_event, trace_exception


@dataclass
class _VariableRowState:
    key: str
    value: str
    key_input: Any | None = None
    value_input: Any | None = None


async def open_project_variables_dialog(
    project: ProjectStatus,
    *,
    template_project_yaml: Path | None = None,
    project_schema_json: Path | None = None,
    before_save: Callable[[], Awaitable[bool]] | None = None,
) -> bool:
    """Open the project variable form and save changed rows to ``project.yaml``."""
    trace_event("ui.variables.open", project=project.project_path, slug=project.metadata.slug)
    try:
        loaded_variables = await asyncio.to_thread(
            read_project_variables,
            project.project_path,
            template_project_yaml=template_project_yaml,
            project_schema_json=project_schema_json,
        )
    except (OSError, ValueError) as exc:
        trace_exception("ui.variables.read_failed", exc, project=project.project_path, slug=project.metadata.slug)
        ui.notify(str(exc), type="negative", multi_line=True)
        return False

    original_rows = [_VariableRowState(variable.key, variable.value) for variable in loaded_variables]
    rows = [_VariableRowState(row.key, row.value) for row in original_rows]
    rows_host: dict[str, Any] = {}
    count_label: dict[str, Any] = {}

    dialog = ui.dialog().props("persistent")

    def _sync_rows_from_inputs() -> None:
        for row in rows:
            if row.key_input is not None:
                row.key = str(row.key_input.value or "")
            if row.value_input is not None:
                row.value = str(row.value_input.value or "")

    def _row_count_text() -> str:
        return f"{len(rows)} variable row{'s' if len(rows) != 1 else ''}"

    def _update_count_label() -> None:
        label = count_label.get("widget")
        if label is not None:
            label.text = _row_count_text()

    def _render_rows() -> None:
        host = rows_host["widget"]
        host.clear()
        with host:
            if not rows:
                with ui.element("div").classes("variable-empty-state"):
                    ui.icon("format_list_bulleted_add").style("font-size: 24px;")
                    ui.label("No narrative variables in project.yaml yet.").classes("empty-title")
                    ui.label("Add a row using a narrative.* name, then save.").classes("empty-body")
            else:
                for group in _group_rows_by_yaml_parent(rows):
                    with ui.element("div").classes("variable-section"):
                        with ui.element("div").classes("variable-section-header"):
                            ui.label(group.label).classes("variable-section-title")
                            ui.label(group.path).classes("variable-section-path")
                        with ui.element("div").classes("variable-header-row"):
                            ui.label("Name")
                            ui.label("Input")
                            ui.label("")
                        for index, row in group.rows:
                            with ui.element("div").classes("variable-row"):
                                row.key_input = (
                                    ui.input(value=row.key, placeholder="narrative.section.variable_name")
                                    .props("outlined dense")
                                    .classes("variable-name-input")
                                )
                                row.value_input = (
                                    ui.textarea(value=row.value, placeholder="Rendered value")
                                    .props("outlined dense autogrow")
                                    .classes("variable-value-input")
                                )
                                ui.button(
                                    icon="delete",
                                    color=None,
                                    on_click=lambda _e, row_index=index: _delete_row(row_index),
                                ).props('flat dense round aria-label="Delete variable row"').classes(
                                    "icon-tool"
                                ).tooltip(
                                    "Delete this variable row"
                                )
        _update_count_label()

    def _add_row() -> None:
        trace_event("ui.variables.add_row.clicked", project=project.project_path)
        _sync_rows_from_inputs()
        rows.append(_VariableRowState("narrative.", ""))
        _render_rows()

    def _delete_row(index: int) -> None:
        trace_event("ui.variables.delete_row.clicked", project=project.project_path, index=index)
        _sync_rows_from_inputs()
        if 0 <= index < len(rows):
            del rows[index]
        _render_rows()

    def _undo() -> None:
        trace_event("ui.variables.undo.clicked", project=project.project_path)
        rows.clear()
        rows.extend(_VariableRowState(row.key, row.value) for row in original_rows)
        _render_rows()
        ui.notify("Variable edits reverted.", type="info")

    async def _save() -> None:
        trace_event("ui.variables.save.clicked", project=project.project_path, slug=project.metadata.slug)
        _sync_rows_from_inputs()
        row_values = [(row.key, row.value) for row in rows if row.key.strip() or row.value.strip()]
        try:
            variables = normalize_project_variables(row_values)
        except ValueError as exc:
            trace_event("ui.variables.validation_failed", project=project.project_path, error=str(exc))
            ui.notify(str(exc), type="negative", multi_line=True)
            return

        if before_save is not None and not await before_save():
            trace_event("ui.variables.save.cancelled_before_write", project=project.project_path)
            return

        try:
            await asyncio.to_thread(write_project_variables, project.project_path, variables)
        except (OSError, ValueError) as exc:
            trace_exception("ui.variables.write_failed", exc, project=project.project_path, slug=project.metadata.slug)
            ui.notify(str(exc), type="negative", multi_line=True)
            return

        trace_event(
            "ui.variables.saved",
            project=project.project_path,
            slug=project.metadata.slug,
            keys=[variable.key for variable in variables],
        )
        dialog.submit(True)

    with dialog, ui.card().classes("variable-dialog-card"):
        with ui.row().classes("w-full items-start gap-3"):
            with ui.column().classes("gap-1").style("flex: 1; min-width: 0;"):
                ui.label("Project variables").classes("dialog-title")
                ui.label(project.metadata.project_title).classes("dialog-subtitle")
            count_label["widget"] = ui.label(_row_count_text()).classes("variable-count")

        ui.label('Edit prose-facing project.yaml values used by <Var k="narrative..." /> shortcodes.').classes(
            "variable-dialog-note"
        )

        rows_host["widget"] = ui.element("div").classes("variable-rows")
        _render_rows()

        with ui.row().classes("w-full justify-between items-center gap-2 mt-3"):
            ui.button("Add variable", icon="add", on_click=_add_row, color=None).props(
                "flat unelevated no-caps"
            ).classes("action-btn")
            with ui.row().classes("items-center gap-2"):
                ui.button("Cancel", on_click=lambda: dialog.submit(False), color=None).props(
                    "flat unelevated no-caps"
                ).classes("action-btn")
                ui.button("Undo", icon="undo", on_click=_undo, color=None).props("flat unelevated no-caps").classes(
                    "action-btn"
                )
                ui.button("Save", icon="save", on_click=_save, color=None).props("flat unelevated no-caps").classes(
                    "action-btn is-warning"
                )

    accepted = await dialog
    trace_event("ui.variables.closed", project=project.project_path, accepted=bool(accepted))
    return bool(accepted)


@dataclass(frozen=True)
class _VariableGroup:
    path: str
    label: str
    rows: list[tuple[int, _VariableRowState]]


def _group_rows_by_yaml_parent(rows: list[_VariableRowState]) -> list[_VariableGroup]:
    groups: list[_VariableGroup] = []
    group_by_path: dict[str, _VariableGroup] = {}
    for index, row in enumerate(rows):
        path = _yaml_parent_path(row.key)
        group = group_by_path.get(path)
        if group is None:
            group = _VariableGroup(path=path, label=_yaml_parent_label(path), rows=[])
            group_by_path[path] = group
            groups.append(group)
        group.rows.append((index, row))
    return groups


def _yaml_parent_path(key: str) -> str:
    parts = [part for part in key.strip().split(".") if part]
    if len(parts) <= 2:
        return "narrative"
    return ".".join(parts[:-1])


def _yaml_parent_label(path: str) -> str:
    parts = path.split(".")
    if parts and parts[0] == "narrative":
        parts = parts[1:]
    if not parts:
        return "Narrative"
    return " / ".join(_humanize_path_part(part) for part in parts)


def _humanize_path_part(value: str) -> str:
    abbreviations = {
        "ach": "ACH",
        "ashrae": "ASHRAE",
        "co2": "CO2",
        "erv": "ERV",
        "ph": "PH",
        "phi": "PHI",
        "phius": "Phius",
    }
    words = value.split("_")
    return " ".join(abbreviations.get(word.lower(), word.capitalize()) for word in words)
