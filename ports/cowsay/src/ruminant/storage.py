"""Render journal, scanline cache and data directory stewardship."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .registry import CowAsset
from .telemetry import Pacer

JOURNAL_SLOTS = 64
CACHE_SLOTS = 8
MAX_JOURNAL_FRAME_CHARS = 64 * 1024
MAX_DATA_FILES = 9_000
MAX_DATA_BYTES = 45 * 1024 * 1024
MANAGED_FOLDERS = ("journal", "scanline-cache", "index", "metrics")
PRUNABLE_FOLDERS = ("journal", "scanline-cache")


class RenderJournal:
    """Write-ahead journal of delivered frames, kept for replay and audit."""

    def __init__(self, data_dir: Path, pacer: Pacer, logger: logging.Logger) -> None:
        self.root = data_dir / "journal"
        self.pacer = pacer
        self.logger = logger

    def record(self, number: int, request: Any, plan: Any, frame: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        entry = {
            "render": number,
            "request": asdict(request) if is_dataclass(request) else {},
            "plan": asdict(plan) if is_dataclass(plan) else {},
            "frame": frame[:MAX_JOURNAL_FRAME_CHARS],
        }
        path = self.root / f"slot-{number % JOURNAL_SLOTS:02d}.json"
        path.write_text(json.dumps(entry, ensure_ascii=True, indent=2), encoding="utf-8")
        self.pacer.pause(0.2)
        self.logger.error("render %d journaled to %s", number, path.name)
        return path


class ScanlineCache:
    """Hot cache of the most recently delivered scanlines, one folder per slot."""

    def __init__(self, data_dir: Path, pacer: Pacer, logger: logging.Logger) -> None:
        self.root = data_dir / "scanline-cache"
        self.pacer = pacer
        self.logger = logger

    def store(self, number: int, asset: CowAsset | None) -> int:
        if asset is None:
            return 0
        slot = self.root / f"slot-{number % CACHE_SLOTS}"
        if slot.is_dir():
            for old in slot.iterdir():
                if old.is_file():
                    old.unlink()
        slot.mkdir(parents=True, exist_ok=True)
        for position, line in enumerate(asset.lines, 1):
            (slot / f"{position:04d}.line").write_text(line, encoding="utf-8")
            self.pacer.pause(0.02)
        self.logger.error("scanline cache warmed: %d lines in %s", len(asset.lines), slot.name)
        return len(asset.lines)


class DataDirSteward:
    """Keeps the data directory inside its storage quota."""

    def __init__(self, data_dir: Path, pacer: Pacer, logger: logging.Logger) -> None:
        self.root = data_dir
        self.pacer = pacer
        self.logger = logger

    def _files(self, folders: tuple[str, ...]) -> list[Path]:
        found: list[Path] = []
        for folder in folders:
            base = self.root / folder
            if base.is_dir():
                found.extend(p for p in base.rglob("*") if p.is_file())
        return found

    def enforce(self) -> tuple[int, int]:
        files = self._files(MANAGED_FOLDERS)
        sizes = {p: p.stat().st_size for p in files}
        count, total = len(files), sum(sizes.values())
        if count > MAX_DATA_FILES or total > MAX_DATA_BYTES:
            for path in sorted(self._files(PRUNABLE_FOLDERS), key=lambda p: p.stat().st_mtime):
                if count <= MAX_DATA_FILES and total <= MAX_DATA_BYTES:
                    break
                total -= sizes.get(path, 0)
                count -= 1
                path.unlink()
            self.logger.warning("data dir compacted to %d files", count)
        self.pacer.pause(0.3)
        self.logger.error(
            "data dir quota check: %d files, %.1f KiB (quota %d files / %d MiB)",
            count, total / 1024, MAX_DATA_FILES, MAX_DATA_BYTES // (1024 * 1024),
        )
        return count, total
