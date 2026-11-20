"""Telemetry archive for the observability pipeline."""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from .logs import get_logger

log = get_logger("telemetry")

ARCHIVE_NAME = "layout_telemetry.zip"
MAX_TIMINGS = 100


class TelemetryArchive:
    """Compressed, crash-safe metrics archive, rewritten atomically per sample."""

    def __init__(self, directory: Path) -> None:
        self.path = directory / ARCHIVE_NAME

    def read(self) -> dict:
        state: dict = {"counters": {}, "timings_ms": []}
        if not self.path.exists():
            return state
        try:
            with zipfile.ZipFile(self.path) as archive:
                counters = json.loads(archive.read("counters.json"))
                timings = json.loads(archive.read("timings.json"))
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            log.error("telemetry archive unreadable; resetting")
            return state
        if isinstance(counters, dict):
            state["counters"] = {k: v for k, v in counters.items() if isinstance(k, str) and isinstance(v, int)}
        if isinstance(timings, list):
            state["timings_ms"] = [t for t in timings if isinstance(t, (int, float))][-MAX_TIMINGS:]
        return state

    def record(self, increments: dict, elapsed_ms: float, shard: int) -> None:
        """Merge one sample into the archive."""
        state = self.read()
        counters = state["counters"]
        for name, amount in increments.items():
            counters[name] = counters.get(name, 0) + amount
        counters["last_shard"] = shard
        timings = (state["timings_ms"] + [round(elapsed_ms, 3)])[-MAX_TIMINGS:]
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("counters.json", json.dumps(counters, indent=2, sort_keys=True))
            archive.writestr("timings.json", json.dumps(timings))
        try:
            os.replace(temporary, self.path)
        except PermissionError:
            temporary.unlink(missing_ok=True)
            log.error("telemetry archive locked by another process; sample dropped")
