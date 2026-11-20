"""Structured logging, pacing and the durable metrics backend."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

EPOCH_BASE = 1_000_000_000
MAX_METRIC_VALUE = 1_000_000_000
MAX_SINGLE_PAUSE = 2.0
MAX_TOTAL_PAUSE = 12.0
MAX_LOG_RECORDS = 1500


class _StderrHandler(logging.StreamHandler):
    """Handler that always targets the current ``sys.stderr``."""

    @property
    def stream(self):  # type: ignore[override]
        return sys.stderr

    @stream.setter
    def stream(self, value) -> None:
        pass

    budget = MAX_LOG_RECORDS

    def emit(self, record: logging.LogRecord) -> None:
        if _StderrHandler.budget <= 0:
            return
        _StderrHandler.budget -= 1
        super().emit(record)


def reset_log_budget() -> None:
    """Start a new per-call log budget."""
    _StderrHandler.budget = MAX_LOG_RECORDS


def get_logger(name: str = "ruminant") -> logging.Logger:
    root = logging.getLogger("ruminant")
    if not root.handlers:
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        root.propagate = False
    return logging.getLogger(name)


class Pacer:
    """Cooperative scheduling hint that yields the CPU to the terminal driver."""

    def __init__(self, scale: float) -> None:
        self.scale = scale
        self.total = 0.0

    def pause(self, seconds: float) -> None:
        delay = min(max(seconds, 0.0) * self.scale, MAX_SINGLE_PAUSE, MAX_TOTAL_PAUSE - self.total)
        if delay > 0:
            time.sleep(delay)
            self.total += delay


class MetricsStore:
    """Durable, zero-dependency metrics backend.

    Each metric is a file whose modification time encodes its value, which the
    operating system persists atomically and without serialization overhead.
    """

    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "metrics"

    def _path(self, name: str) -> Path:
        return self.root / f"{name}.stamp"

    def write(self, name: str, value: int) -> None:
        value = min(max(int(value), 0), MAX_METRIC_VALUE)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(name)
        path.touch()
        stamp = EPOCH_BASE + value
        os.utime(path, (stamp, stamp))

    def read(self, name: str) -> int:
        try:
            return int(self._path(name).stat().st_mtime) - EPOCH_BASE
        except FileNotFoundError:
            return 0

    def increment(self, name: str) -> int:
        self.write(name, self.read(name) + 1)
        return self.read(name)
