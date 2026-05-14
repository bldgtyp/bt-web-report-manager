"""Trace logging for support/debugging.

The Manager is often launched from Finder, where environment and PATH state
are hard to infer after the fact. Keep a durable, detailed local trace so setup
and project-bootstrap failures can be diagnosed without guessing.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

APP_SUPPORT_ENV = "BTWR_MANAGER_APP_SUPPORT"
TRACE_LOG_ENV = "BTWR_MANAGER_TRACE_LOG"

LOGGER_NAME = "bt_web_report_manager.trace"
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_BACKUP_COUNT = 5


def trace_log_path() -> Path:
    override = os.environ.get(TRACE_LOG_ENV)
    if override:
        return Path(override).expanduser()
    app_support = Path(os.environ.get(APP_SUPPORT_ENV, "~/Library/Application Support/bt-web-report-manager"))
    return app_support.expanduser() / "logs" / "manager-trace.log"


def configure_trace_logging() -> Path:
    path = trace_log_path()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in tuple(logger.handlers):
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) != path:
            logger.removeHandler(handler)
            handler.close()
    if not any(
        isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == path for handler in logger.handlers
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=DEFAULT_MAX_BYTES, backupCount=DEFAULT_BACKUP_COUNT)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s pid=%(process)d event=%(message)s", "%Y-%m-%dT%H:%M:%S%z")
        )
        logger.addHandler(handler)
    return path


def trace_event(event: str, **fields: Any) -> None:
    try:
        configure_trace_logging()
        logger = logging.getLogger(LOGGER_NAME)
        logger.info("%s %s", event, _format_fields(fields))
    except OSError:
        return


def trace_exception(event: str, exc: BaseException, **fields: Any) -> None:
    try:
        configure_trace_logging()
        logger = logging.getLogger(LOGGER_NAME)
        logger.exception("%s %s exception=%s", event, _format_fields(fields), repr(exc))
    except OSError:
        return


def _format_fields(fields: dict[str, Any]) -> str:
    parts = []
    for key in sorted(fields):
        parts.append(f"{key}={_format_value(fields[key])}")
    return " ".join(parts)


def _format_value(value: Any) -> str:
    if isinstance(value, Path):
        return repr(str(value))
    if isinstance(value, (list, tuple)):
        return repr([str(item) if isinstance(item, Path) else item for item in value])
    if isinstance(value, dict):
        return repr({key: str(item) if isinstance(item, Path) else item for key, item in value.items()})
    return repr(value)
