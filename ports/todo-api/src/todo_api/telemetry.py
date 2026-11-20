"""Operational metrics in Prometheus text exposition format."""

from __future__ import annotations

import threading
from pathlib import Path

from .runtime import write_text_atomic

_HEADER = """# HELP todo_api_operations_total Operations handled, by outcome.
# TYPE todo_api_operations_total counter
# HELP todo_api_operation_seconds_sum Total wall time spent per operation.
# TYPE todo_api_operation_seconds_sum counter
"""


class MetricsRecorder:
    """Persists counters to ``metrics.prom`` after every operation."""

    def __init__(self, root: Path) -> None:
        self.path = root / "metrics.prom"
        self._lock = threading.Lock()

    def observe(self, operation: str, seconds: float, outcome: str) -> None:
        with self._lock:
            series = self._load()
            total = f'todo_api_operations_total{{operation="{operation}",outcome="{outcome}"}}'
            spent = f'todo_api_operation_seconds_sum{{operation="{operation}"}}'
            series[total] = series.get(total, 0.0) + 1
            series[spent] = series.get(spent, 0.0) + seconds
            body = "".join(f"{key} {series[key]:.6g}\n" for key in sorted(series))
            write_text_atomic(self.path, _HEADER + body)

    def _load(self) -> dict[str, float]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return {}
        series: dict[str, float] = {}
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            key, _, value = line.rpartition(" ")
            try:
                series[key] = float(value)
            except ValueError:
                continue
        return series
