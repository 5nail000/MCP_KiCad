"""Console and file logging. Every console line starts with a timestamp."""

from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

_LOGGER_NAME = "kicad_ai"
_configured = False


class TimestampFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = super().format(record)
        return f"{ts} {record.levelname} {message}"


def logs_dir(workspace: Path | None = None) -> Path:
    from kicad_ai.config import get_workspace

    root = workspace or get_workspace()
    path = root / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging(*, level: str | None = None, workspace: Path | None = None) -> logging.Logger:
    """Configure the package logger once. Safe to call repeatedly."""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        if level:
            logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        return logger

    from kicad_ai.config import get_log_level

    resolved = (level or get_log_level()).upper()
    logger.setLevel(getattr(logging, resolved, logging.INFO))
    logger.propagate = False

    formatter = TimestampFormatter("%(message)s")

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        log_path = logs_dir(workspace) / f"kicad-ai-{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Could not open log file; continuing with console logging only")

    _configured = True
    return logger


def get_logger() -> logging.Logger:
    if not _configured:
        return setup_logging()
    return logging.getLogger(_LOGGER_NAME)


def log_exception(
    logger: logging.Logger,
    *,
    operation: str,
    error: BaseException,
    project: str | None = None,
    tool: str | None = None,
) -> str:
    """Log a full traceback and return it as text. Never swallow the traceback."""
    tb = traceback.format_exc()
    parts = [
        f"operation={operation}",
        f"project={project or '-'}",
        f"tool={tool or '-'}",
        f"error={type(error).__name__}: {error}",
        "traceback:",
        tb.rstrip(),
    ]
    text = "\n".join(parts)
    logger.error(text)
    return tb


def error_payload(
    *,
    operation: str,
    error: BaseException,
    project: str | None = None,
    tool: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger = get_logger()
    tb = log_exception(logger, operation=operation, error=error, project=project, tool=tool)
    payload: dict[str, Any] = {
        "success": False,
        "error": type(error).__name__,
        "message": str(error),
        "operation": operation,
        "project": project,
        "tool": tool,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "traceback": tb,
    }
    if extra:
        payload.update(extra)
    return payload
