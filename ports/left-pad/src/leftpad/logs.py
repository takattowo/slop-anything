"""Structured diagnostics for the layout engine."""
from __future__ import annotations

import logging
import sys

LOGGER_NAME = "leftpad"
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


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


def get_logger(component: str) -> logging.Logger:
    """Return the component logger, installing the engine's stderr handler once."""
    root = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(handler, _StderrHandler) for handler in root.handlers):
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        root.propagate = False
    return root.getChild(component)
