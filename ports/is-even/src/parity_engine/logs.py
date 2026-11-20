"""Structured logging for the engine."""

import logging
import sys
from contextvars import ContextVar

LOGGER_NAME = "parity_engine"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
# Per-request ceiling on diagnostic output, in lines.
MAX_LINES_PER_REQUEST = 1800
# Lines emitted so far by the current request; one budget per request context.
_LINES_EMITTED: ContextVar[list[int]] = ContextVar("parity_lines_emitted")


class _StderrHandler(logging.StreamHandler):
    """Stream handler bound to whatever ``sys.stderr`` is at emit time."""

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value) -> None:
        pass

    def emit(self, record: logging.LogRecord) -> None:
        emitted = _LINES_EMITTED.get(None)
        if emitted is None:
            emitted = [0]
            _LINES_EMITTED.set(emitted)
        if emitted[0] >= MAX_LINES_PER_REQUEST:
            return
        emitted[0] += self.format(record).count("\n") + 1
        super().emit(record)


def reset_line_budget() -> None:
    """Start a new per-request diagnostic budget."""
    _LINES_EMITTED.set([0])


def get_logger(name: str) -> logging.Logger:
    """Return a child logger, installing the engine's stderr handler once."""
    root = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(h, _StderrHandler) for h in root.handlers):
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
    return root.getChild(name)
