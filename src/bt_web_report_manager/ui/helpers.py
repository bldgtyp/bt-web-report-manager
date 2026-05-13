"""Pure formatting + disabled-reason helpers shared by the UI layer.

Extracted from the old ``main_window.py`` unchanged so they can be tested
without spinning up NiceGUI. Every function here is pure (no I/O except a
single ``package.json`` read in ``open_editor_disabled_reason``).
"""

from __future__ import annotations

import json
from datetime import datetime

from bt_web_report_manager.models import ProjectStatus


def format_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def git_label(project: ProjectStatus) -> str:
    if not project.git.is_repo:
        return "No git"
    branch = project.git.branch or "detached"
    sync: list[str] = []
    if project.git.ahead:
        sync.append(f"{project.git.ahead} ahead")
    if project.git.behind:
        sync.append(f"{project.git.behind} behind")
    sync_text = f" ({', '.join(sync)})" if sync else ""
    if project.git.dirty_count:
        return f"{branch}, {project.git.dirty_count} dirty{sync_text}"
    return f"{branch}, clean{sync_text}"


def lock_label(project: ProjectStatus) -> str:
    lock = project.lock
    if lock is None:
        return "-"
    if lock.malformed:
        return f"Malformed lock at {lock.path}"
    owner = lock.user or "unknown"
    host = lock.host or "unknown host"
    expiry = format_dt(lock.expires_at)
    return f"{owner} on {host}, expires {expiry}"


def lock_table_label(project: ProjectStatus) -> str:
    lock = project.lock
    if lock is None:
        return "-"
    if lock.malformed:
        return "Malformed"
    if lock.user is None:
        return "Unknown owner"
    return lock.user


def client_building_label(project: ProjectStatus) -> str:
    values = [value for value in (project.metadata.client_name, project.metadata.building_name) if value]
    return " / ".join(values) if values else "-"


def status_explanations(project: ProjectStatus) -> list[str]:
    lines: list[str] = []
    if project.manifest_path is None:
        lines.append("- No data manifest exists yet; run Scrape after the PHPP path is configured.")
    elif project.needs_scrape:
        lines.append("- PHPP is newer than the data manifest; run Scrape before previewing or publishing.")
    else:
        lines.append("- Data is current against the configured PHPP workbook.")

    if not project.git.is_repo:
        lines.append("- Project folder is not a git worktree; Commit & push is unavailable.")
    elif project.git.dirty_count:
        lines.append(f"- Git has {project.git.dirty_count} uncommitted change(s).")
    else:
        lines.append("- Git worktree is clean.")

    if project.git.ahead:
        lines.append(f"- Current branch is {project.git.ahead} commit(s) ahead of upstream.")
    if project.git.behind:
        lines.append(f"- Current branch is {project.git.behind} commit(s) behind upstream; v1 does not auto-pull.")
    if project.lock is not None:
        lines.append(f"- Lock state: {lock_label(project)}.")
    if project.warnings:
        lines.append("- Project warnings need review before relying on status badges.")
    return lines


def action_explanations(project: ProjectStatus, running: bool) -> list[str]:
    states = {
        "Scrape": scrape_disabled_reason(project, running, True),
        "Dev preview": selected_disabled_reason(project, running, True),
        "Reveal": selected_disabled_reason(project, running, True),
        "Open editor": open_editor_disabled_reason(project, running, True),
        "Open code editor": selected_disabled_reason(project, running, True),
        "Commit & push": commit_disabled_reason(project, running, True),
    }
    return [
        f"- {name}: {'enabled' if reason is None else reason.removeprefix('Disabled: ')}"
        for name, reason in states.items()
    ]


def selected_disabled_reason(project: ProjectStatus | None, running: bool, enabled: bool) -> str | None:
    if not enabled or project is None:
        return "Disabled: no project selected."
    if running:
        return "Disabled: another command is running."
    return None


def open_editor_disabled_reason(project: ProjectStatus | None, running: bool, enabled: bool) -> str | None:
    reason = selected_disabled_reason(project, running, enabled)
    if reason is not None:
        return reason
    assert project is not None
    package_path = project.project_path / "package.json"
    if not package_path.exists():
        return "Disabled: package.json is missing."
    try:
        package_json = json.loads(package_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return f"Disabled: package.json is unreadable ({exc})."
    if not isinstance(package_json.get("scripts"), dict) or "dev:editor" not in package_json["scripts"]:
        return "Disabled: package.json does not define dev:editor."
    return None


def scrape_disabled_reason(project: ProjectStatus | None, running: bool, enabled: bool) -> str | None:
    reason = selected_disabled_reason(project, running, enabled)
    if reason is not None:
        return reason
    assert project is not None
    if project.metadata.phpp_path is None:
        return "Disabled: project.yaml does not define source_files.phpp_path."
    if not project.metadata.phpp_path.exists():
        return "Disabled: configured PHPP workbook is missing."
    return None


def commit_disabled_reason(project: ProjectStatus | None, running: bool, enabled: bool) -> str | None:
    reason = selected_disabled_reason(project, running, enabled)
    if reason is not None:
        return reason
    assert project is not None
    if not project.git.is_repo:
        return "Disabled: project folder is not a git worktree."
    if project.git.dirty_count == 0:
        return "Disabled: git worktree is clean."
    return None


def suggest_commit_message(project: ProjectStatus) -> str:
    if project.needs_scrape:
        return f"Update {project.metadata.slug} report data"
    return f"Update {project.metadata.slug} report"
