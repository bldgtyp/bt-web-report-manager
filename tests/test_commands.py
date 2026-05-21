from pathlib import Path

from pytest import MonkeyPatch

from bt_web_report_manager.commands import (
    commit_push_command,
    dev_preview_command,
    executable_search_paths,
    resolve_executable,
    node_toolchain_bin_dirs,
    open_code_editor_command,
    open_editor_command,
    renderer_bin_dirs,
    run_command,
    scrape_command,
    tool_status,
)
from bt_web_report_manager.models import GitStatus, ManagerSettings, ProjectMetadata, ProjectStatus


def test_tool_status_reports_missing_executable() -> None:
    status = tool_status("missing", "btwr-manager-missing-tool-for-test")

    assert not status.ok
    assert status.path is None
    assert "not found" in status.message


def test_action_command_specs(tmp_path: Path) -> None:
    project = ProjectStatus(
        project_path=tmp_path,
        metadata=ProjectMetadata("slug", "Project", None, None, None, None, tmp_path / "data", None),
        git=GitStatus(False),
    )
    renderer = tmp_path / "renderer"
    settings = ManagerSettings(
        btwr_executable="btwr-dev",
        pnpm_executable="pnpm-dev",
        renderer_source=renderer,
        editor_command="code-dev",
    )

    assert scrape_command(project, settings).args == ("btwr-dev", "scrape", str(tmp_path))
    assert scrape_command(project, settings).refresh_on_success
    assert dev_preview_command(project, settings).args == (
        "btwr-dev",
        "preview",
        str(tmp_path),
        "--pnpm",
        "pnpm-dev",
        "--renderer-source",
        str(renderer),
    )
    assert dev_preview_command(project, settings).long_running
    assert open_editor_command(project, settings).args == (
        "btwr-dev",
        "editor",
        str(tmp_path),
        "--pnpm",
        "pnpm-dev",
        "--renderer-source",
        str(renderer),
    )
    assert open_editor_command(project, settings).cwd == tmp_path
    assert open_editor_command(project, settings).long_running
    assert open_code_editor_command(project, settings).args == ("code-dev", str(tmp_path))
    commit = commit_push_command(project, settings, "Update report")
    assert commit.args[0:2] == ("/bin/sh", "-lc")
    assert "remote get-url origin" in commit.args[2]
    assert " add -A -- . ':!.bldgtyp/lock.yaml'" in commit.args[2]
    assert "git diff --cached --quiet" in commit.args[2]
    assert "git commit -m 'Update report'" in commit.args[2]
    assert "git push -u origin HEAD" in commit.args[2]
    assert commit.refresh_on_success


def test_commit_push_command_pushes_without_committing_lock_file(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    project_path = tmp_path / "project"
    run_command(["git", "init", "--bare", str(remote)])
    run_command(["git", "init", str(project_path)])
    run_command(["git", "config", "user.email", "test@example.com"], cwd=project_path)
    run_command(["git", "config", "user.name", "Test User"], cwd=project_path)
    run_command(["git", "branch", "-M", "main"], cwd=project_path)
    run_command(["git", "remote", "add", "origin", str(remote)], cwd=project_path)
    (project_path / "README.md").write_text("initial\n")
    run_command(["git", "add", "README.md"], cwd=project_path)
    run_command(["git", "commit", "-m", "Initial"], cwd=project_path)
    run_command(["git", "push", "-u", "origin", "main"], cwd=project_path)

    (project_path / "README.md").write_text("updated\n")
    lock_dir = project_path / ".bldgtyp"
    lock_dir.mkdir()
    (lock_dir / "lock.yaml").write_text("user: ed\n")
    project = ProjectStatus(
        project_path=project_path,
        metadata=ProjectMetadata("slug", "Project", None, None, None, None, project_path / "data", None),
        git=GitStatus(True, branch="main", dirty_count=2),
    )

    spec = commit_push_command(project, ManagerSettings(), "Update report")
    result = run_command(spec.args, cwd=spec.cwd)

    assert result.returncode == 0, result.stderr
    tracked = run_command(["git", "ls-files"], cwd=project_path)
    assert "README.md" in tracked.stdout
    assert ".bldgtyp/lock.yaml" not in tracked.stdout
    remote_log = run_command(["git", "log", "--oneline", "origin/main", "-1"], cwd=project_path)
    assert "Update report" in remote_log.stdout


def test_commit_push_command_succeeds_when_only_lock_file_is_dirty(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    project_path = tmp_path / "project"
    run_command(["git", "init", "--bare", str(remote)])
    run_command(["git", "init", str(project_path)])
    run_command(["git", "config", "user.email", "test@example.com"], cwd=project_path)
    run_command(["git", "config", "user.name", "Test User"], cwd=project_path)
    run_command(["git", "branch", "-M", "main"], cwd=project_path)
    run_command(["git", "remote", "add", "origin", str(remote)], cwd=project_path)
    (project_path / "README.md").write_text("initial\n")
    run_command(["git", "add", "README.md"], cwd=project_path)
    run_command(["git", "commit", "-m", "Initial"], cwd=project_path)
    run_command(["git", "push", "-u", "origin", "main"], cwd=project_path)
    initial_head = run_command(["git", "rev-parse", "HEAD"], cwd=project_path).stdout.strip()

    lock_dir = project_path / ".bldgtyp"
    lock_dir.mkdir()
    (lock_dir / "lock.yaml").write_text("user: ed\n")
    project = ProjectStatus(
        project_path=project_path,
        metadata=ProjectMetadata("slug", "Project", None, None, None, None, project_path / "data", None),
        git=GitStatus(True, branch="main", dirty_count=1),
    )

    spec = commit_push_command(project, ManagerSettings(), "Update report")
    result = run_command(spec.args, cwd=spec.cwd)

    assert result.returncode == 0, result.stderr
    assert "No project changes to commit" in result.stdout
    current_head = run_command(["git", "rev-parse", "HEAD"], cwd=project_path).stdout.strip()
    assert current_head == initial_head


def test_commit_push_command_fails_before_commit_when_origin_missing(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    run_command(["git", "init", str(project_path)])
    run_command(["git", "config", "user.email", "test@example.com"], cwd=project_path)
    run_command(["git", "config", "user.name", "Test User"], cwd=project_path)
    run_command(["git", "branch", "-M", "main"], cwd=project_path)
    (project_path / "README.md").write_text("initial\n")
    project = ProjectStatus(
        project_path=project_path,
        metadata=ProjectMetadata("slug", "Project", None, None, None, None, project_path / "data", None),
        git=GitStatus(True, branch="main", dirty_count=1),
    )

    spec = commit_push_command(project, ManagerSettings(), "Update report")
    result = run_command(spec.args, cwd=spec.cwd)

    assert result.returncode != 0
    assert "No such remote 'origin'" in result.stderr
    log = run_command(["git", "log", "--oneline"], cwd=project_path)
    assert log.returncode != 0


def test_resolve_executable_uses_manager_search_path(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "tool"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    assert resolve_executable("tool") == str(executable)


def test_resolve_executable_uses_app_support_renderer_bin(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    support_dir = tmp_path / "support"
    bin_dir = support_dir / "renderer" / "current" / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "wrangler"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    monkeypatch.setenv("BTWR_MANAGER_APP_SUPPORT", str(support_dir))
    monkeypatch.setenv("PATH", "")

    assert renderer_bin_dirs()[0] == bin_dir
    assert str(bin_dir) in executable_search_paths()
    assert resolve_executable("wrangler") == str(executable)


def test_executable_search_path_prefers_nvm_node(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    node_bin = home / ".nvm" / "versions" / "node" / "v22.22.2" / "bin"
    node_bin.mkdir(parents=True)
    node = node_bin / "node"
    node.write_text("#!/bin/sh\nexit 0\n")
    node.chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/local/bin")

    assert node_toolchain_bin_dirs() == (node_bin,)
    assert executable_search_paths().index(str(node_bin)) < executable_search_paths().index("/usr/local/bin")


def test_resolve_executable_rejects_non_executable_explicit_path(tmp_path: Path) -> None:
    candidate = tmp_path / "tool"
    candidate.write_text("#!/bin/sh\nexit 0\n")
    candidate.chmod(0o644)

    assert resolve_executable(str(candidate)) is None
