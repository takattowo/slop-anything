"""Structured JSON logging to stderr."""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

ROOT_LOGGER = "todo_api"


class JsonFormatter(logging.Formatter):
    """Renders each record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
        payload: dict[str, Any] = {
            "ts": f"{stamp}.{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update(getattr(record, "fields", None) or {})
        return json.dumps(payload, default=str)


class StderrHandler(logging.Handler):
    """Writes to whatever ``sys.stderr`` is at emit time."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stderr.write(self.format(record) + "\n")
            sys.stderr.flush()
        except Exception:  # pragma: no cover - logging must never raise
            self.handleError(record)


def configure_logging() -> None:
    """Install the JSON handler once per process."""
    root = logging.getLogger(ROOT_LOGGER)
    if any(isinstance(h, StderrHandler) for h in root.handlers):
        return
    handler = StderrHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT_LOGGER}.{name}")


def emit(logger: logging.Logger, level: int, message: str, /, **fields: Any) -> None:
    """Log ``message`` with structured ``fields``."""
    logger.log(level, message, extra={"fields": fields})
