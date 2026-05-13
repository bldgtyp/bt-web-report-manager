"""btwr-manager entry point."""

from bt_web_report_manager.app import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
