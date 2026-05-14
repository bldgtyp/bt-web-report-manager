from pathlib import Path

from bt_web_report_manager.ui.command_feedback import (
    ScrapeRunFeedback,
    scrape_error_summary,
    scrape_success_summary,
)


def test_scrape_success_summary_names_written_folder() -> None:
    feedback = ScrapeRunFeedback(
        project_title="Sample Project",
        project_slug="sample",
        project_path=Path("/tmp/Sample/04_Web"),
        data_dir=Path("/tmp/Sample/04_Web/data"),
        args=("btwr", "scrape", "/tmp/Sample/04_Web"),
        cwd=Path("/tmp/Sample/04_Web"),
    )

    summary = scrape_success_summary(feedback)

    assert "Scrape completed successfully." in summary
    assert "Files written to:\n/tmp/Sample/04_Web/data" in summary
    assert "Command: btwr scrape /tmp/Sample/04_Web" in summary


def test_scrape_error_summary_includes_exit_code_and_full_output() -> None:
    feedback = ScrapeRunFeedback(
        project_title="Sample Project",
        project_slug="sample",
        project_path=Path("/tmp/Sample/04_Web"),
        data_dir=Path("/tmp/Sample/04_Web/data"),
        args=("btwr", "scrape", "/tmp/Sample/04_Web"),
        cwd=Path("/tmp/Sample/04_Web"),
        output_lines=["Reading PHPP", "Missing worksheet: Areas"],
    )

    summary = scrape_error_summary(feedback, exit_code=2, canceled=False)

    assert "Scrape failed." in summary
    assert "Exit code: 2" in summary
    assert "Expected output folder: /tmp/Sample/04_Web/data" in summary
    assert "Reading PHPP\nMissing worksheet: Areas" in summary


def test_scrape_error_summary_handles_no_output() -> None:
    feedback = ScrapeRunFeedback(
        project_title="Sample Project",
        project_slug="sample",
        project_path=Path("/tmp/Sample/04_Web"),
        data_dir=Path("/tmp/Sample/04_Web/data"),
        args=("btwr", "scrape", "/tmp/Sample/04_Web"),
        cwd=Path("/tmp/Sample/04_Web"),
    )

    summary = scrape_error_summary(feedback, exit_code=-1, canceled=False)

    assert "No output was captured before the command ended." in summary
