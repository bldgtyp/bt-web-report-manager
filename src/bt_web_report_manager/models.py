"""Typed shapes shared by the manager services and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ToolStatus:
    name: str
    executable: str
    path: str | None
    version: str | None
    ok: bool
    message: str


@dataclass(frozen=True)
class ManagerSettings:
    projects_root: Path = Path("~/Dropbox/bldgtyp").expanduser()
    extra_project_paths: tuple[Path, ...] = ()
    hidden_project_paths: tuple[Path, ...] = ()
    btwr_executable: str = "btwr"
    pnpm_executable: str = "pnpm"
    # Renderer (template) source is only consulted at SEED time — by `btwr new`
    # and `btwr re-seed`. Once a project has been seeded, its own vendored
    # src/, tina/, scripts/ replace this entirely at preview/build/editor time.
    renderer_source: Path | None = None
    git_executable: str = "git"
    gh_executable: str = "gh"
    editor_command: str = "code"
    github_owner: str = "bldgtyp"
    github_repo: str = "bt-web-report-manager"
    project_github_owner: str = "bldgtyp-projects"
    lock_ttl_hours: int = 4


@dataclass(frozen=True)
class ProjectMetadata:
    slug: str
    project_title: str
    client_name: str | None
    building_name: str | None
    phase: str | None
    phpp_path: Path | None
    data_dir: Path
    production_url: str | None


@dataclass(frozen=True)
class GitStatus:
    is_repo: bool
    branch: str | None = None
    dirty_count: int = 0
    ahead: int = 0
    behind: int = 0
    remote: str | None = None
    last_commit: str | None = None


@dataclass(frozen=True)
class LockInfo:
    path: Path
    user: str | None = None
    host: str | None = None
    project_slug: str | None = None
    opened_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    malformed: bool = False

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now


@dataclass(frozen=True)
class PlatformInfo:
    """Contents of ``<project>/.bldgtyp/platform.yaml`` if present.

    Stamped by ``btwr new`` at seed time and updated by ``btwr re-seed``.
    Projects from before the vendored model have no platform.yaml — the
    Manager UI degrades to "unknown" badges in that case.
    """

    renderer_seed_ref: str | None = None
    schemas_pin: str | None = None
    cli_version: str | None = None
    seeded_at: datetime | None = None

    @property
    def is_vendored(self) -> bool:
        """True if any provenance was recorded — i.e. this is a Phase-3 seed."""

        return self.renderer_seed_ref is not None


@dataclass(frozen=True)
class ProjectStatus:
    project_path: Path
    metadata: ProjectMetadata
    git: GitStatus
    lock: LockInfo | None = None
    manifest_path: Path | None = None
    manifest_generated_at: datetime | None = None
    phpp_modified_at: datetime | None = None
    warnings: tuple[str, ...] = ()
    badges: tuple[str, ...] = field(default_factory=tuple)
    platform: PlatformInfo | None = None

    @property
    def needs_scrape(self) -> bool:
        if self.manifest_path is None:
            return True
        if self.manifest_generated_at is None:
            return self.phpp_modified_at is not None
        if self.phpp_modified_at is None:
            return False
        return self.phpp_modified_at > self.manifest_generated_at
