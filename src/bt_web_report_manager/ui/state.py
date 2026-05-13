"""Mutable application state shared across UI components.

NiceGUI's reactive model is callback-driven, so we keep all mutable state on
a single ``ManagerState`` instance rather than scattering globals. UI
builders take ``state`` and a ``rerender`` callback; mutations are followed
by an explicit ``rerender()`` call when anything observable changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bt_web_report_manager.models import ManagerSettings, ProjectStatus


@dataclass
class ManagerState:
    settings: ManagerSettings
    projects: list[ProjectStatus] = field(default_factory=list)
    selected_slug: str | None = None
    owned_lock_paths: set[Path] = field(default_factory=set)

    def selected_project(self) -> ProjectStatus | None:
        if self.selected_slug is None:
            return None
        for project in self.projects:
            if project.metadata.slug == self.selected_slug:
                return project
        return None

    def select_project_by_path(self, path: Path | None) -> None:
        if path is None:
            self.selected_slug = None
            return
        for project in self.projects:
            if project.project_path == path:
                self.selected_slug = project.metadata.slug
                return
        self.selected_slug = None

    def select_first_if_unset(self) -> None:
        if self.selected_slug is None and self.projects:
            self.selected_slug = self.projects[0].metadata.slug
