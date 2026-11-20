"""Telemetry export."""

from __future__ import annotations

import os
from pathlib import Path


class MarkdownMetrics:
    """Publishes per-request engine telemetry as a Markdown table for dashboards."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def write(self, metrics: dict[str, object]) -> None:
        lines = ["# Parity engine telemetry", "", "| metric | value |", "|---|---|"]
        lines += [f"| {key} | {value} |" for key, value in sorted(metrics.items())]
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
