"""New project planning for the manager wizard."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from bt_web_report_manager.commands import CommandSpec, run_command
from bt_web_report_manager.models import ManagerSettings

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
BT_NUMBER_RE = re.compile(r"^(\d{4})(?:\D|$)")
IGNORED_EXISTING_NAMES = {".DS_Store", ".localized", "Icon\r", "desktop.ini", "Thumbs.db"}


@dataclass(frozen=True)
class NewProjectPlan:
    project_title: str
    slug: str
    client_name: str | None
    building_name: str | None
    phase: str | None
    local_folder: Path
    target_web_path: Path
    phpp_path: Path | None
    repo_name: str
    repo_owner: str
    production_url: str
    overwrite_existing: bool = False

    @property
    def relative_phpp_path(self) -> str | None:
        if self.phpp_path is None:
            return None
        return os.path.relpath(self.phpp_path, self.target_web_path)

    def summary_lines(self) -> list[str]:
        phpp = str(self.phpp_path) if self.phpp_path is not None else "None configured"
        return [
            f"Project title: {self.project_title}",
            f"Slug: {self.slug}",
            f"Client: {self.client_name or '-'}",
            f"Building: {self.building_name or '-'}",
            f"Phase: {self.phase or '-'}",
            f"Local folder: {self.local_folder}",
            f"Target 04_Web path: {self.target_web_path}",
            f"PHPP workbook: {phpp}",
            f"GitHub repo: {self.repo_owner}/{self.repo_name}",
            f"Production URL: {self.production_url}",
            f"Overwrite existing 04_Web contents: {'yes' if self.overwrite_existing else 'no'}",
        ]

    def manual_checklist(self) -> list[str]:
        phpp_line = (
            f"Set source_files.phpp_path to {self.relative_phpp_path}"
            if self.phpp_path is not None
            else "Leave source_files.phpp_path empty until the PHPP workbook is ready."
        )
        return [
            "Phase 7 dependency: btwr new is not implemented in the configured CLI yet.",
            "",
            "Manual checklist:",
            f"1. Create or verify project folder: {self.local_folder}",
            f"2. {'Replace contents of' if self.overwrite_existing else 'Create target web folder'}: {self.target_web_path}",
            f"3. Create private GitHub repo: {self.repo_owner}/{self.repo_name}",
            "4. Run btwr new to create a content-only 04_Web payload.",
            "5. Write or confirm project.yaml with the metadata shown above.",
            f"6. {phpp_line}",
            f"7. Set publishing.production_url to {self.production_url}",
            "8. Git init, first commit, and push main. Do not install Node dependencies in 04_Web.",
            "9. Configure Cloudflare Pages and reserve the production subdomain.",
        ]


@dataclass(frozen=True)
class BootstrapCommandStatus:
    available: bool
    executable: str
    resolved_path: str | None
    message: str
    stdout: str = ""
    stderr: str = ""


def build_new_project_plan(
    *,
    project_title: str,
    slug: str,
    client_name: str | None,
    building_name: str | None,
    phase: str | None,
    local_folder: Path | str,
    target_web_path: Path | str,
    phpp_path: Path | str | None,
    repo_name: str,
    production_url: str,
    repo_owner: str = "bldgtyp-projects",
    overwrite_existing: bool = False,
) -> NewProjectPlan:
    plan = NewProjectPlan(
        project_title=project_title.strip(),
        slug=sanitize_slug(slug),
        client_name=_clean_optional(client_name),
        building_name=_clean_optional(building_name),
        phase=_clean_optional(phase),
        local_folder=coerce_user_path(local_folder),
        target_web_path=coerce_user_path(target_web_path),
        phpp_path=coerce_user_path(phpp_path) if phpp_path is not None else None,
        repo_name=repo_name.strip(),
        repo_owner=repo_owner.strip(),
        production_url=production_url.strip(),
        overwrite_existing=overwrite_existing,
    )
    errors = validate_new_project_plan(plan)
    if errors:
        raise ValueError("\n".join(errors))
    return plan


def clean_path_text(value: str | None) -> str:
    """Normalize path text pasted from Finder's Copy as Pathname."""
    if value is None:
        return ""
    text = value.strip()
    quote_pairs = (("'", "'"), ('"', '"'), ("\u2018", "\u2019"), ("\u201c", "\u201d"))
    for start, end in quote_pairs:
        if len(text) >= 2 and text.startswith(start) and text.endswith(end):
            return text[1:-1].strip()
    return text


def coerce_user_path(value: Path | str) -> Path:
    return Path(clean_path_text(str(value))).expanduser()


def sanitize_slug(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def default_slug_from_project_folder(local_folder: Path | str) -> str:
    name = coerce_user_path(local_folder).name
    match = BT_NUMBER_RE.match(name)
    if match:
        return f"project-{match.group(1)}"
    return sanitize_slug(name)


def repo_name_from_slug(slug: str) -> str:
    clean_slug = sanitize_slug(slug)
    return f"bt-proj-{clean_slug}" if clean_slug else ""


def production_url_from_slug(slug: str) -> str:
    clean_slug = sanitize_slug(slug)
    return f"https://{clean_slug}.bldgtyp.com" if clean_slug else ""


def meaningful_existing_items(target: Path) -> list[Path]:
    if not target.exists():
        return []
    return [item for item in target.iterdir() if item.name not in IGNORED_EXISTING_NAMES]


def validate_new_project_plan(plan: NewProjectPlan) -> list[str]:
    errors: list[str] = []
    if not plan.project_title:
        errors.append("Project title is required.")
    if not SLUG_RE.fullmatch(plan.slug):
        errors.append("Slug must be lowercase kebab-case, using only a-z, 0-9, and single hyphens.")
    if not plan.local_folder.is_absolute():
        errors.append("Local folder must be an absolute path.")
    elif plan.local_folder.exists() and not plan.local_folder.is_dir():
        errors.append("Local folder already exists and is not a directory.")
    if not plan.target_web_path.is_absolute():
        errors.append("Target 04_Web path must be an absolute path.")
    elif plan.target_web_path.exists() and not plan.target_web_path.is_dir():
        errors.append("Target 04_Web path already exists and is not a directory.")
    if plan.target_web_path.name != "04_Web":
        errors.append("Target web path must end in 04_Web.")
    if plan.local_folder in plan.target_web_path.parents:
        pass
    elif plan.local_folder != plan.target_web_path.parent:
        errors.append("Target 04_Web path must live inside the local project folder.")
    existing_items = meaningful_existing_items(plan.target_web_path)
    if existing_items and not plan.overwrite_existing:
        item_list = ", ".join(item.name for item in existing_items[:5])
        suffix = "" if len(existing_items) <= 5 else f", and {len(existing_items) - 5} more"
        errors.append(f"Target 04_Web path already exists and is not empty: {item_list}{suffix}.")
    if plan.phpp_path is not None:
        if not plan.phpp_path.is_absolute():
            errors.append("PHPP path must be absolute when provided.")
        elif not plan.phpp_path.exists():
            errors.append("PHPP workbook does not exist.")
        elif plan.phpp_path.suffix.lower() not in {".xlsx", ".xlsm"}:
            errors.append("PHPP workbook must be an .xlsx or .xlsm file.")
    if not REPO_RE.fullmatch(plan.repo_name):
        errors.append("Repo name can only use letters, numbers, hyphens, underscores, and periods.")
    if not REPO_RE.fullmatch(plan.repo_owner):
        errors.append("Repo owner can only use letters, numbers, hyphens, underscores, and periods.")
    if plan.repo_name != repo_name_from_slug(plan.slug):
        errors.append(f"Repo name must be {repo_name_from_slug(plan.slug)}.")
    parsed = urlparse(plan.production_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        errors.append("Production URL must be an https origin URL without a path.")
    expected_host = f"{plan.slug}.bldgtyp.com"
    if parsed.netloc and parsed.netloc != expected_host:
        errors.append(f"Production URL host must be {expected_host}.")
    return errors


def bootstrap_command_available(settings: ManagerSettings) -> bool:
    return bootstrap_command_status(settings).available


def bootstrap_command_status(settings: ManagerSettings) -> BootstrapCommandStatus:
    executable = settings.btwr_executable
    resolved = shutil.which(executable)
    if resolved is None:
        return BootstrapCommandStatus(
            available=False,
            executable=executable,
            resolved_path=None,
            message=f"{executable} was not found on the Manager PATH. Set the btwr executable in Settings.",
        )
    try:
        result = run_command([resolved, "new", "--help"], timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        return BootstrapCommandStatus(
            available=False,
            executable=executable,
            resolved_path=resolved,
            message=str(exc),
        )
    if result.returncode != 0:
        return BootstrapCommandStatus(
            available=False,
            executable=executable,
            resolved_path=resolved,
            message=f"{resolved} new --help exited {result.returncode}.",
            stdout=result.stdout,
            stderr=result.stderr,
        )
    if "Create a content-only report repo" not in result.stdout and "--slug" not in result.stdout:
        return BootstrapCommandStatus(
            available=False,
            executable=executable,
            resolved_path=resolved,
            message=f"{resolved} does not look like the expected bt-web-report CLI.",
            stdout=result.stdout,
            stderr=result.stderr,
        )
    return BootstrapCommandStatus(
        available=True,
        executable=executable,
        resolved_path=resolved,
        message=f"{resolved} supports btwr new.",
        stdout=result.stdout,
        stderr=result.stderr,
    )


def bootstrap_command(plan: NewProjectPlan, settings: ManagerSettings) -> CommandSpec:
    args = [
        settings.btwr_executable,
        "new",
        str(plan.target_web_path),
        "--slug",
        plan.slug,
        "--title",
        plan.project_title,
        "--repo",
        plan.repo_name,
        "--production-url",
        plan.production_url,
    ]
    if plan.client_name:
        args.extend(["--client", plan.client_name])
    if plan.building_name:
        args.extend(["--building", plan.building_name])
    if plan.phase:
        args.extend(["--phase", plan.phase])
    if plan.phpp_path:
        args.extend(["--phpp", str(plan.phpp_path)])
    if plan.overwrite_existing:
        args.append("--overwrite")
    if settings.renderer_source is not None:
        args.extend(["--renderer-source", str(settings.renderer_source)])
    return CommandSpec(
        name="New project",
        args=tuple(args),
        cwd=plan.local_folder,
        refresh_on_success=True,
    )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
