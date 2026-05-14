"""Pure formatting + disabled-reason helpers shared by the UI layer.

Extracted from the old ``main_window.py`` unchanged so they can be tested
without spinning up NiceGUI. Every function here is pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path

from bt_web_report_manager.models import ProjectStatus


@dataclass(frozen=True)
class ProjectMetric:
    label: str
    value: int


@dataclass(frozen=True)
class ActionCardState:
    key: str
    label: str
    detail: str
    enabled: bool
    tooltip: str


@dataclass(frozen=True)
class FileLocation:
    key: str
    label: str
    kind: str
    value: str
    path: Path | None = None
    url: str | None = None


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


def badge_kind(badge: str) -> str:
    low = badge.lower()
    if low == "data current" or low == "git clean":
        return "success"
    if low.startswith("locked by you"):
        return "accent"
    if low.startswith("needs scrape") or low.startswith("dirty") or low.startswith("locked by"):
        return "warning"
    if "malformed" in low or "no data" in low or "no git" in low or "stale" in low or "warnings" in low:
        return "danger"
    return "neutral"


def badge_tooltip(badge: str) -> str:
    low = badge.lower()
    if low == "data current":
        return "PHPP data has been scraped and the data manifest is current."
    if low == "git clean":
        return "Git worktree has no uncommitted changes."
    if low.startswith("dirty"):
        return (
            "Git worktree has uncommitted changes. Count comes from git status and includes staged, "
            "unstaged, and untracked entries."
        )
    if low == "needs scrape":
        return "PHPP workbook is newer than the data manifest; run Scrape PHPP before previewing or publishing."
    if low == "no data":
        return "No scraped data manifest exists yet; run Scrape PHPP."
    if low == "no git":
        return "Project folder is not a git worktree; Commit & push is unavailable."
    if low.startswith("locked by you"):
        return "You hold the project write lock."
    if low.startswith("locked by"):
        return "Another user holds the project write lock."
    if "stale" in low:
        return "Project write lock has expired or needs refresh."
    if "malformed" in low:
        return "Project write lock file could not be parsed."
    if low == "warnings":
        return "Project status has warnings; review the status detail before relying on this project."
    return badge


def badges_html(badges: tuple[str, ...]) -> str:
    items: list[str] = []
    for badge in badges:
        tooltip = escape(badge_tooltip(badge), quote=True)
        items.append(
            f'<span class="chip chip-{badge_kind(badge)}" title="{tooltip}" aria-label="{tooltip}">'
            f"{escape(badge)}</span>"
        )
    return "".join(items)


def client_building_label(project: ProjectStatus) -> str:
    values = [value for value in (project.metadata.client_name, project.metadata.building_name) if value]
    return " / ".join(values) if values else "-"


def project_metrics(projects: list[ProjectStatus]) -> list[ProjectMetric]:
    return [
        ProjectMetric("Projects", len(projects)),
        ProjectMetric("Dirty git", sum(1 for project in projects if project.git.dirty_count)),
        ProjectMetric("Need scrape", sum(1 for project in projects if project.needs_scrape)),
        ProjectMetric("Warnings", sum(1 for project in projects if project.warnings)),
    ]


def project_row(project: ProjectStatus) -> dict[str, str]:
    return {
        "name": project.metadata.project_title,
        "slug": project.metadata.slug,
        "client_building": client_building_label(project),
        "phase": project.metadata.phase or "-",
        "phpp": format_dt(project.phpp_modified_at),
        "data": format_dt(project.manifest_generated_at),
        "git": git_label(project),
        "lock": lock_table_label(project),
        "deploy": "Unknown",
        "badges": ", ".join(project.badges),
        "badges_html": badges_html(project.badges),
    }


def action_card_states(project: ProjectStatus | None, running: bool, enabled: bool) -> dict[str, ActionCardState]:
    reasons = {
        "scrape": scrape_disabled_reason(project, running, enabled),
        "dev": selected_disabled_reason(project, running, enabled),
        "editor": open_editor_disabled_reason(project, running, enabled),
        "code_editor": selected_disabled_reason(project, running, enabled),
        "commit": commit_disabled_reason(project, running, enabled),
        "reveal": selected_disabled_reason(project, running, enabled),
    }
    details = {
        "scrape": ("Scrape PHPP", "Refresh data from PHPP"),
        "dev": ("Dev preview", "Serve on localhost:4321"),
        "editor": ("Open editor (TinaCMS)", "Edit content visually"),
        "code_editor": ("Open code editor", "Open project in the configured editor"),
        "commit": ("Commit & push", "Commit pending changes and push"),
        "reveal": ("Reveal in Finder", "Show project folder"),
    }
    return {
        key: ActionCardState(
            key=key,
            label=details[key][0],
            detail=details[key][1],
            enabled=reason is None,
            tooltip=reason or details[key][1],
        )
        for key, reason in reasons.items()
    }


def project_file_locations(project: ProjectStatus) -> list[FileLocation]:
    locations = [
        FileLocation("web_root", "Web root", "WEB", str(project.project_path), path=project.project_path),
    ]
    locations.append(
        FileLocation(
            "phpp",
            "PHPP workbook",
            "XLSX",
            str(project.metadata.phpp_path) if project.metadata.phpp_path is not None else "Not configured",
            path=project.metadata.phpp_path,
        )
    )
    if project.manifest_path is not None:
        locations.append(
            FileLocation("manifest", "Manifest", "JSON", str(project.manifest_path), path=project.manifest_path)
        )
    else:
        manifest_path = project.metadata.data_dir / "manifest.json"
        locations.append(FileLocation("manifest", "Manifest", "JSON", str(manifest_path), path=manifest_path))
    if project.metadata.production_url:
        locations.append(
            FileLocation(
                "live_site",
                "Live site",
                "URL",
                project.metadata.production_url,
                url=project.metadata.production_url,
            )
        )
    return locations


def status_explanations(project: ProjectStatus) -> list[str]:
    lines: list[str] = []
    if project.manifest_path is None:
        lines.append("- No data manifest exists yet; run Scrape after the PHPP path is configured.")
    elif project.manifest_generated_at is None:
        lines.append("- Starter data manifest has not been scraped from PHPP yet; run Scrape PHPP.")
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
    if project.git.remote is None:
        return "Disabled: git remote 'origin' is not configured."
    return None


def suggest_commit_message(project: ProjectStatus) -> str:
    if project.needs_scrape:
        return f"Update {project.metadata.slug} report data"
    return f"Update {project.metadata.slug} report"
