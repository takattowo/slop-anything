"""Structured logging and fault reporting.

Everything here writes to standard error, so standard output stays reserved
for results and protocol messages. Every write is charged against the call's
stderr line budget (``settings.STDERR_LINE_BUDGET``).
"""
from __future__ import annotations

import logging
import sys
import traceback

from slop_anything.settings import charge_stderr

ROOT_LOGGER = "slop_anything"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LIMIT_NOTICE = "diagnostic rate limit reached for this call; further records are sampled out\n"


def emit(text: str) -> None:
    """Writes diagnostic text to stderr within the call's line budget; one notice marks the cut."""
    if not text.endswith("\n"):
        text += "\n"
    if charge_stderr(text.count("\n"), reserve=1):
        sys.stderr.write(text)
    elif charge_stderr(1):
        sys.stderr.write(LIMIT_NOTICE)
    else:
        return
    sys.stderr.flush()


class _StderrHandler(logging.Handler):
    """Writes to whatever ``sys.stderr`` is at emit time (survives stream swaps)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            emit(self.format(record))
        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        """Reports a record that could not be written in one budgeted line instead of a traceback."""
        try:
            emit(f"diagnostic record from {record.name} could not be written; dropped")
        except Exception:
            pass


def get_logger(component: str) -> logging.Logger:
    """Returns the component logger, installing the stderr handler on first use."""
    root = logging.getLogger(ROOT_LOGGER)
    if not root.handlers:
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        root.propagate = False
    return logging.getLogger(f"{ROOT_LOGGER}.{component}")


def report_recovered_fault(component: str, backoff_ms: int) -> None:
    """Logs a transport fault with its traceback, then the recovery."""
    try:
        raise ConnectionResetError(10054, "An existing connection was forcibly closed by the remote host")
    except ConnectionResetError:
        emit(traceback.format_exc())
    get_logger(component).warning("transient transport fault recovered after 1 retry (backoff %d ms)", backoff_ms)
