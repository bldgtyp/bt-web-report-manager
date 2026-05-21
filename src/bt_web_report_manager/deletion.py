"""Full project cleanup for Manager-owned report projects."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

from bt_web_report_manager.commands import command_executable, run_command
from bt_web_report_manager.models import ManagerSettings, ProjectStatus
from bt_web_report_manager.settings import cleanup_project_runtime, project_runtime_dirs
from bt_web_report_manager.trace import trace_event, trace_exception

CLOUDFLARE_API_BASE_URL = "https://api.cloudflare.com/client/v4"


@dataclass(frozen=True)
class DeleteResource:
    label: str
    value: str
    action: str
    enabled: bool = True


@dataclass(frozen=True)
class ProjectDeletePlan:
    slug: str
    project_title: str
    local_path: Path
    runtime_dirs: tuple[Path, ...]
    github_repo: str | None
    cloudflare_pages_project: str | None
    cloudflare_custom_domain: str | None
    resources: tuple[DeleteResource, ...]


@dataclass(frozen=True)
class DeleteStepResult:
    label: str
    ok: bool
    message: str


@dataclass(frozen=True)
class ProjectDeleteResult:
    ok: bool
    steps: tuple[DeleteStepResult, ...]
    removed_runtime_dirs: tuple[Path, ...] = ()
    removed_local_path: Path | None = None


@dataclass(frozen=True)
class CloudflareCredentials:
    token: str
    account_id: str


class ProjectDeleteError(RuntimeError):
    """Raised when a full delete cannot safely continue."""


def build_project_delete_plan(project: ProjectStatus) -> ProjectDeletePlan:
    """Return the irreversible cleanup plan that the UI should show before deleting."""
    github_repo = github_repo_from_remote(project.git.remote)
    project_yaml_pages = cloudflare_pages_project_from_project_yaml(project.project_path)
    cloudflare_pages_project = project_yaml_pages or repo_name_from_full_name(github_repo)
    cloudflare_custom_domain = hostname_from_url(project.metadata.production_url)
    runtime_dirs = project_runtime_dirs(project.metadata.slug)

    resources = (
        DeleteResource("Local report folder", str(project.project_path), "Delete folder"),
        DeleteResource(
            "Manager runtime folders",
            ", ".join(str(path) for path in runtime_dirs),
            "Delete if present",
        ),
        DeleteResource(
            "GitHub repository",
            github_repo or "Not detected from origin remote",
            "Delete remote repository" if github_repo else "Skip",
            enabled=github_repo is not None,
        ),
        DeleteResource(
            "Cloudflare custom domains",
            cloudflare_custom_domain or "Not configured in project.yaml",
            "Detach configured domain and any domains Cloudflare reports for this Pages project",
            enabled=cloudflare_pages_project is not None,
        ),
        DeleteResource(
            "Cloudflare Pages project",
            cloudflare_pages_project or "Not configured in project.yaml or origin remote",
            "Delete Pages project" if cloudflare_pages_project else "Skip",
            enabled=cloudflare_pages_project is not None,
        ),
        DeleteResource(
            "PHPP workbook",
            str(project.metadata.phpp_path) if project.metadata.phpp_path is not None else "Not configured",
            "Not deleted unless it is inside the local report folder",
            enabled=False,
        ),
    )
    plan = ProjectDeletePlan(
        slug=project.metadata.slug,
        project_title=project.metadata.project_title,
        local_path=project.project_path,
        runtime_dirs=runtime_dirs,
        github_repo=github_repo,
        cloudflare_pages_project=cloudflare_pages_project,
        cloudflare_custom_domain=cloudflare_custom_domain,
        resources=resources,
    )
    trace_event("deletion.plan.built", plan=_plan_trace(plan))
    return plan


def format_project_delete_confirmation(plan: ProjectDeletePlan) -> str:
    lines = [
        "Full cleanup delete is permanent. It removes the report project artifacts listed below.",
        "",
        f"Project: {plan.project_title}",
        f"Slug: {plan.slug}",
        "",
    ]
    for resource in plan.resources:
        prefix = "-" if resource.enabled else "- skipped:"
        lines.append(f"{prefix} {resource.label}: {resource.value}")
        lines.append(f"  action: {resource.action}")
    lines.extend(
        [
            "",
            "Remote cleanup runs first. The local report folder is deleted only after remote cleanup succeeds.",
        ]
    )
    return "\n".join(lines)


def delete_project_artifacts(plan: ProjectDeletePlan, settings: ManagerSettings) -> ProjectDeleteResult:
    """Delete remote artifacts first, then Manager runtime and local report files."""
    trace_event("deletion.execute.start", plan=_plan_trace(plan))
    _validate_local_delete_path(plan.local_path)
    steps: list[DeleteStepResult] = []

    if plan.cloudflare_pages_project:
        cloudflare_steps = delete_cloudflare_pages(
            pages_project=plan.cloudflare_pages_project,
            custom_domain=plan.cloudflare_custom_domain,
            settings=settings,
        )
        steps.extend(cloudflare_steps)
        failure = _first_failure(steps)
        if failure is not None:
            trace_event("deletion.execute.halt_after_cloudflare", failure=failure)
            return ProjectDeleteResult(False, tuple(steps))
    else:
        steps.append(DeleteStepResult("Cloudflare", True, "Skipped; no Pages project configured."))

    if plan.github_repo:
        step = delete_github_repo(plan.github_repo, settings)
        steps.append(step)
        if not step.ok:
            trace_event("deletion.execute.halt_after_github", failure=step)
            return ProjectDeleteResult(False, tuple(steps))
    else:
        steps.append(DeleteStepResult("GitHub repository", True, "Skipped; no GitHub origin remote detected."))

    try:
        removed_runtime_dirs = cleanup_project_runtime(plan.slug)
    except Exception as exc:
        trace_exception("deletion.runtime.cleanup_failed", exc, slug=plan.slug)
        steps.append(DeleteStepResult("Manager runtime folders", False, f"Failed to remove runtime folders: {exc}"))
        return ProjectDeleteResult(False, tuple(steps))
    steps.append(
        DeleteStepResult(
            "Manager runtime folders",
            True,
            f"Removed {len(removed_runtime_dirs)} folder(s).",
        )
    )
    try:
        _delete_local_path(plan.local_path)
    except Exception as exc:
        trace_exception("deletion.local.delete_failed", exc, path=plan.local_path)
        steps.append(DeleteStepResult("Local report folder", False, f"Failed to delete {plan.local_path}: {exc}"))
        return ProjectDeleteResult(False, tuple(steps), removed_runtime_dirs)
    steps.append(DeleteStepResult("Local report folder", True, f"Deleted {plan.local_path}."))
    delete_result = ProjectDeleteResult(True, tuple(steps), removed_runtime_dirs, plan.local_path)
    trace_event("deletion.execute.done", result=delete_result)
    return delete_result


def delete_github_repo(repo: str, settings: ManagerSettings) -> DeleteStepResult:
    gh = command_executable(settings.gh_executable)
    command = [gh, "repo", "delete", repo, "--yes"]
    trace_event("deletion.github.delete.start", repo=repo, command=command)
    try:
        result = run_command(command, timeout=45)
    except Exception as exc:
        trace_exception("deletion.github.delete.exception", exc, repo=repo)
        return DeleteStepResult("GitHub repository", False, f"Failed to delete {repo}: {exc}")

    output = _command_output(result.stdout, result.stderr)
    if result.returncode == 0:
        return DeleteStepResult("GitHub repository", True, f"Deleted {repo}.")
    if github_delete_not_found(output):
        return DeleteStepResult("GitHub repository", True, f"{repo} was already absent.")
    message = output or f"gh exited {result.returncode}"
    return DeleteStepResult("GitHub repository", False, f"Failed to delete {repo}: {message}")


def delete_cloudflare_pages(
    *,
    pages_project: str,
    custom_domain: str | None,
    settings: ManagerSettings,
) -> tuple[DeleteStepResult, ...]:
    trace_event("deletion.cloudflare.delete.start", pages_project=pages_project, custom_domain=custom_domain)
    try:
        credentials = resolve_cloudflare_credentials(settings)
    except ProjectDeleteError as exc:
        return (DeleteStepResult("Cloudflare", False, str(exc)),)

    steps: list[DeleteStepResult] = []
    domain_names = {custom_domain} if custom_domain else set()
    listed_domains = _cloudflare_pages_domains(credentials, pages_project)
    if not listed_domains.ok:
        return (DeleteStepResult("Cloudflare custom domains", False, listed_domains.message),)
    domain_names.update(listed_domains.domains)

    if domain_names:
        for domain_name in sorted(domain_names):
            domain_result = _cloudflare_delete(
                credentials,
                f"/pages/projects/{pages_project}/domains/{domain_name}",
                allow_not_found=True,
            )
            steps.append(
                DeleteStepResult(
                    "Cloudflare custom domain",
                    domain_result.ok,
                    domain_result.message if not domain_result.ok else f"Detached {domain_name} from {pages_project}.",
                )
            )
            if not domain_result.ok:
                return tuple(steps)
    else:
        steps.append(
            DeleteStepResult(
                "Cloudflare custom domains",
                True,
                "Skipped; no custom domains configured or reported by Cloudflare.",
            )
        )

    project_result = _cloudflare_delete(credentials, f"/pages/projects/{pages_project}", allow_not_found=True)
    steps.append(
        DeleteStepResult(
            "Cloudflare Pages project",
            project_result.ok,
            project_result.message if not project_result.ok else f"Deleted {pages_project}.",
        )
    )
    return tuple(steps)


def resolve_cloudflare_credentials(settings: ManagerSettings) -> CloudflareCredentials:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if token:
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
        if not account_id:
            account_id = _single_cloudflare_account_id(token)
        return CloudflareCredentials(token, account_id)

    _refresh_wrangler_oauth(settings)
    token = _wrangler_oauth_token()
    if not token:
        raise ProjectDeleteError(
            "Cloudflare cleanup needs CLOUDFLARE_API_TOKEN or a local Wrangler OAuth login. Run `wrangler login`."
        )
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
    if not account_id:
        account_id = _single_cloudflare_account_id(token)
    return CloudflareCredentials(token, account_id)


@dataclass(frozen=True)
class _CloudflareApiResult:
    ok: bool
    message: str


@dataclass(frozen=True)
class _CloudflareDomainsResult:
    ok: bool
    message: str
    domains: tuple[str, ...] = ()


def _cloudflare_pages_domains(credentials: CloudflareCredentials, pages_project: str) -> _CloudflareDomainsResult:
    path = f"/pages/projects/{pages_project}/domains"
    encoded_path = "/".join(_encode_cloudflare_path_part(part) for part in path.strip("/").split("/"))
    url = f"{CLOUDFLARE_API_BASE_URL}/accounts/{credentials.account_id}/{encoded_path}"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {credentials.token}"}, timeout=30)
        payload = _json_payload(response)
    except requests.RequestException as exc:
        return _CloudflareDomainsResult(False, f"Cloudflare API request failed: {exc}")
    if response.status_code == 404:
        return _CloudflareDomainsResult(True, "Cloudflare Pages project was already absent.")
    if not response.ok or payload.get("success", True) is False:
        return _CloudflareDomainsResult(False, _cloudflare_error_message(response.status_code, payload))
    result = payload.get("result")
    if not isinstance(result, list):
        return _CloudflareDomainsResult(False, "Cloudflare Pages domains response was not a list.")
    domains: list[str] = []
    for item in result:
        name = item.get("name") if isinstance(item, dict) else None
        if isinstance(name, str) and name:
            domains.append(name)
    return _CloudflareDomainsResult(True, "Cloudflare Pages domains read.", tuple(domains))


def _cloudflare_delete(
    credentials: CloudflareCredentials, account_path: str, *, allow_not_found: bool = False
) -> _CloudflareApiResult:
    encoded_path = "/".join(_encode_cloudflare_path_part(part) for part in account_path.strip("/").split("/"))
    url = f"{CLOUDFLARE_API_BASE_URL}/accounts/{credentials.account_id}/{encoded_path}"
    try:
        response = requests.delete(url, headers={"Authorization": f"Bearer {credentials.token}"}, timeout=30)
        payload = _json_payload(response)
    except requests.RequestException as exc:
        return _CloudflareApiResult(False, f"Cloudflare API request failed: {exc}")
    if allow_not_found and response.status_code == 404:
        return _CloudflareApiResult(True, "Cloudflare resource was already absent.")
    if response.ok and payload.get("success", True) is not False:
        return _CloudflareApiResult(True, "Cloudflare delete succeeded.")
    return _CloudflareApiResult(False, _cloudflare_error_message(response.status_code, payload))


def _single_cloudflare_account_id(token: str) -> str:
    try:
        response = requests.get(
            f"{CLOUDFLARE_API_BASE_URL}/accounts",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        payload = _json_payload(response)
    except requests.RequestException as exc:
        raise ProjectDeleteError(f"Could not read Cloudflare accounts: {exc}") from exc
    if not response.ok or payload.get("success", True) is False:
        raise ProjectDeleteError(_cloudflare_error_message(response.status_code, payload))
    accounts = payload.get("result")
    if not isinstance(accounts, list) or not accounts:
        raise ProjectDeleteError("Cloudflare account lookup returned no accounts.")
    if len(accounts) > 1:
        raise ProjectDeleteError("Multiple Cloudflare accounts found; set CLOUDFLARE_ACCOUNT_ID before deleting.")
    account_id = accounts[0].get("id") if isinstance(accounts[0], dict) else None
    if not isinstance(account_id, str) or not account_id:
        raise ProjectDeleteError("Cloudflare account lookup did not return an account id.")
    return account_id


def _refresh_wrangler_oauth(settings: ManagerSettings) -> None:
    wrangler = command_executable("wrangler")
    try:
        result = run_command([wrangler, "whoami"], timeout=30)
    except Exception as exc:
        trace_exception("deletion.cloudflare.wrangler_whoami.exception", exc, wrangler=wrangler)
        return
    trace_event(
        "deletion.cloudflare.wrangler_whoami",
        returncode=result.returncode,
        stdout_preview=result.stdout[-1000:],
        stderr_preview=result.stderr[-1000:],
        wrangler=wrangler,
    )


def _wrangler_oauth_token() -> str | None:
    for path in _wrangler_config_paths():
        if not path.exists():
            continue
        text = path.read_text()
        match = re.search(r'oauth_token\s*=\s*"([^"]+)"', text)
        if match:
            trace_event("deletion.cloudflare.wrangler_token.found", path=path)
            return match.group(1)
    trace_event("deletion.cloudflare.wrangler_token.missing")
    return None


def _wrangler_config_paths() -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / "Library/Preferences/.wrangler/config/default.toml",
        home / ".config/.wrangler/config/default.toml",
        home / ".wrangler/config/default.toml",
    )


def _json_payload(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"success": False, "errors": [{"message": response.text.strip()}]}
    return payload if isinstance(payload, dict) else {"success": False, "errors": [{"message": str(payload)}]}


def _cloudflare_error_message(status_code: int, payload: dict[str, Any]) -> str:
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        messages = []
        for error in errors:
            if isinstance(error, dict):
                message = error.get("message")
                code = error.get("code")
                if isinstance(message, str):
                    messages.append(f"{message} [code: {code}]" if code is not None else message)
        if messages:
            return f"Cloudflare API failed ({status_code}): {'; '.join(messages)}"
    return f"Cloudflare API failed ({status_code})."


def _encode_cloudflare_path_part(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def _validate_local_delete_path(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ProjectDeleteError(f"Local report folder does not exist: {resolved}")
    if not resolved.is_dir():
        raise ProjectDeleteError(f"Local report path is not a folder: {resolved}")
    if not (resolved / "project.yaml").exists():
        raise ProjectDeleteError(f"Refusing to delete a folder without project.yaml: {resolved}")
    if resolved == Path.home() or resolved.parent == resolved:
        raise ProjectDeleteError(f"Refusing to delete unsafe path: {resolved}")


def _delete_local_path(path: Path) -> None:
    resolved = path.expanduser().resolve()
    trace_event("deletion.local.delete.start", path=resolved)
    if resolved.is_symlink():
        resolved.unlink()
    else:
        shutil.rmtree(resolved)
    trace_event("deletion.local.delete.done", path=resolved)


def cloudflare_pages_project_from_project_yaml(project_path: Path) -> str | None:
    project_yaml = project_path / "project.yaml"
    if not project_yaml.exists():
        return None
    try:
        raw = yaml.safe_load(project_yaml.read_text()) or {}
    except Exception as exc:
        trace_exception("deletion.project_yaml.read_failed", exc, project_yaml=project_yaml)
        return None
    if not isinstance(raw, dict):
        return None
    publishing = raw.get("publishing")
    if not isinstance(publishing, dict):
        return None
    value = publishing.get("cloudflare_pages_project")
    return value.strip() if isinstance(value, str) and value.strip() else None


def hostname_from_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    return parsed.hostname


def github_repo_from_remote(remote: str | None) -> str | None:
    if not remote:
        return None
    patterns = (
        r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.match(pattern, remote.strip())
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return None


def repo_name_from_full_name(repo: str | None) -> str | None:
    if repo is None:
        return None
    _, _, name = repo.partition("/")
    return name or None


def github_delete_not_found(output: str) -> bool:
    lowered = output.lower()
    return "could not resolve to a repository" in lowered or "not found" in lowered or "404" in lowered


def _command_output(stdout: str, stderr: str) -> str:
    return "\n".join(part.strip() for part in (stdout, stderr) if part.strip())


def _first_failure(steps: list[DeleteStepResult]) -> DeleteStepResult | None:
    for step in steps:
        if not step.ok:
            return step
    return None


def _plan_trace(plan: ProjectDeletePlan) -> dict[str, object]:
    return {
        "slug": plan.slug,
        "local_path": plan.local_path,
        "github_repo": plan.github_repo,
        "cloudflare_pages_project": plan.cloudflare_pages_project,
        "cloudflare_custom_domain": plan.cloudflare_custom_domain,
    }
