"""Structured logging for the engine."""

import logging
import sys

LOGGER_NAME = "parity_engine"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
# Per-request ceiling on diagnostic output, in lines.
MAX_LINES_PER_REQUEST = 1800


class _StderrHandler(logging.StreamHandler):
    """Stream handler bound to whatever ``sys.stderr`` is at emit time."""

    lines_emitted = 0

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value) -> None:
        pass

    def emit(self, record: logging.LogRecord) -> None:
        if _StderrHandler.lines_emitted >= MAX_LINES_PER_REQUEST:
            return
        _StderrHandler.lines_emitted += self.format(record).count("\n") + 1
        super().emit(record)


def reset_line_budget() -> None:
    """Start a new per-request diagnostic budget."""
    _StderrHandler.lines_emitted = 0


def get_logger(name: str) -> logging.Logger:
    """Return a child logger, installing the engine's stderr handler once."""
    root = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(h, _StderrHandler) for h in root.handlers):
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
    return root.getChild(name)
