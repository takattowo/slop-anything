"""Telemetry export."""

from __future__ import annotations

import os
from pathlib import Path

from .logs import get_logger

_log = get_logger("metrics")


class MarkdownMetrics:
    """Publishes per-request engine telemetry as a Markdown table for dashboards."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def write(self, metrics: dict[str, object]) -> None:
        lines = ["# Parity engine telemetry", "", "| metric | value |", "|---|---|"]
        lines += [f"| {key} | {value} |" for key, value in sorted(metrics.items())]
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            os.replace(tmp, self.path)
        except PermissionError:
            tmp.unlink(missing_ok=True)
            _log.error("telemetry table is held open by another process; export skipped")
