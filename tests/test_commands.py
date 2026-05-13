from pathlib import Path

from bt_web_report_manager.commands import (
    commit_push_command,
    dev_preview_command,
    open_code_editor_command,
    open_editor_command,
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
    settings = ManagerSettings(btwr_executable="btwr-dev", pnpm_executable="pnpm-dev", editor_command="code-dev")

    assert scrape_command(project, settings).args == ("btwr-dev", "scrape", str(tmp_path))
    assert scrape_command(project, settings).refresh_on_success
    assert dev_preview_command(project, settings).args == ("pnpm-dev", "dev")
    assert dev_preview_command(project, settings).long_running
    assert open_editor_command(project, settings).args == ("pnpm-dev", "dev:editor")
    assert open_editor_command(project, settings).cwd == tmp_path
    assert open_editor_command(project, settings).long_running
    assert open_code_editor_command(project, settings).args == ("code-dev", str(tmp_path))
    commit = commit_push_command(project, settings, "Update report")
    assert commit.args[0:2] == ("/bin/sh", "-lc")
    assert "git add -A -- . ':!.bldgtyp/lock.yaml'" in commit.args[2]
    assert "git commit -m 'Update report'" in commit.args[2]
    assert "git push" in commit.args[2]
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
