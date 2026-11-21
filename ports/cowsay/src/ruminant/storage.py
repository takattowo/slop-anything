"""Render journal, scanline cache and data directory stewardship."""

from __future__ import annotations

import json
import logging
import stat
from dataclasses import asdict, is_dataclass
from itertools import islice
from pathlib import Path
from typing import Any

from .registry import MAX_LINES_PER_COW, CowAsset
from .telemetry import Pacer

JOURNAL_SLOTS = 64
CACHE_SLOTS = 8
MAX_JOURNAL_FRAME_CHARS = 64 * 1024
MAX_DATA_FILES = 9_000
MAX_DATA_BYTES = 45 * 1024 * 1024
MAX_SCAN_ENTRIES = 20_000
JOURNAL_NAMES = frozenset(f"slot-{n:02d}.json" for n in range(JOURNAL_SLOTS))
CACHE_SLOT_NAMES = frozenset(f"slot-{n}" for n in range(CACHE_SLOTS))
CACHE_LINE_NAMES = frozenset(f"{n:04d}.line" for n in range(1, MAX_LINES_PER_COW + 1))


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
        slot.mkdir(parents=True, exist_ok=True)
        for position in range(1, MAX_LINES_PER_COW + 1):
            (slot / f"{position:04d}.line").unlink(missing_ok=True)
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

    def _usage(self) -> tuple[int, int]:
        count = total = 0
        for path in islice(self.root.rglob("*"), MAX_SCAN_ENTRIES):
            try:
                info = path.stat()
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                count += 1
                total += info.st_size
        return count, total

    @staticmethod
    def _is_link(path: Path) -> bool:
        return path.is_symlink() or path.is_junction()

    @classmethod
    def _matching(cls, folder: Path, names: frozenset[str], want_dir: bool) -> list[Path]:
        """Entries of ``folder`` named in ``names``; links, junctions and folders gone mid-scan yield nothing."""
        try:
            if cls._is_link(folder) or not folder.is_dir():
                return []
            entries = list(islice(folder.iterdir(), MAX_SCAN_ENTRIES))
        except OSError:
            return []
        found = [p for p in entries if p.name in names]
        return [p for p in found if not cls._is_link(p) and p.is_dir()] if want_dir else found

    def _own_files(self) -> list[tuple[float, str, int, Path]]:
        """Journal slots and cached scanlines, matched by the exact names this module writes.

        One lstat per file: (mtime, path, size, path). Links and files another run removed mid-scan are skipped.
        """
        candidates = self._matching(self.root / "journal", JOURNAL_NAMES, want_dir=False)
        for slot in self._matching(self.root / "scanline-cache", CACHE_SLOT_NAMES, want_dir=True):
            candidates.extend(self._matching(slot, CACHE_LINE_NAMES, want_dir=False))
        own = []
        for path in candidates:
            try:
                info = path.lstat()
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                own.append((info.st_mtime, str(path), info.st_size, path))
        return own

    def enforce(self) -> tuple[int, int]:
        count, total = self._usage()
        if count > MAX_DATA_FILES or total > MAX_DATA_BYTES:
            for _, _, size, path in sorted(self._own_files()):
                if count <= MAX_DATA_FILES and total <= MAX_DATA_BYTES:
                    break
                try:
                    path.unlink()
                except OSError:
                    continue
                total -= size
                count -= 1
            self.logger.warning("data dir compacted to %d files", count)
        self.pacer.pause(0.3)
        self.logger.error(
            "data dir quota check: %d files, %.1f KiB (quota %d files / %d MiB)",
            count, total / 1024, MAX_DATA_FILES, MAX_DATA_BYTES // (1024 * 1024),
        )
        return count, total
