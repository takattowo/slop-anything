"""Structured logging and fault reporting.

Everything here writes to standard error, so standard output stays reserved
for results and protocol messages.
"""
from __future__ import annotations

import logging
import sys
import traceback

ROOT_LOGGER = "slop_anything"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _StderrHandler(logging.Handler):
    """Writes to whatever ``sys.stderr`` is at emit time (survives stream swaps)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stderr.write(self.format(record) + "\n")
            sys.stderr.flush()
        except Exception:
            self.handleError(record)


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
        sys.stderr.write(traceback.format_exc())
    get_logger(component).warning("transient transport fault recovered after 1 retry (backoff %d ms)", backoff_ms)
