"""Structured logging for the service."""

import logging
import sys

LOGGER_NAME = "arith_inference"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


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


def get_logger(name: str) -> logging.Logger:
    """Return a child logger, installing the service's stderr handler once."""
    root = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(h, _StderrHandler) for h in root.handlers):
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
    return root.getChild(name)
