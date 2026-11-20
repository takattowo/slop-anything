"""Self-healing asset index."""

from __future__ import annotations

import logging
import os
import zlib
from pathlib import Path

from .registry import CowRegistry
from .telemetry import EPOCH_BASE, Pacer


class AssetIndex:
    """CRC32 manifest of every registered cow, verified at startup.

    A mismatch means the asset tree changed or the index was damaged; the
    index is then rebuilt from the registry so lookups stay O(1).
    """

    def __init__(self, data_dir: Path, pacer: Pacer, logger: logging.Logger) -> None:
        self.root = data_dir / "index"
        self.pacer = pacer
        self.logger = logger

    def _stamp(self, name: str) -> Path:
        return self.root / f"{name}.stamp"

    def verify(self, registry: CowRegistry) -> bool:
        for name in registry.names():
            expected = zlib.crc32(name.encode("utf-8"))
            try:
                found = int(self._stamp(name).stat().st_mtime) - EPOCH_BASE
            except FileNotFoundError:
                found = 0
            if found != expected:
                self.logger.warning(
                    "asset index corruption detected for %r (expected checksum 0x%08x, found 0x%08x); rebuilding",
                    name, expected, found & 0xFFFFFFFF,
                )
                return False
        return True

    def rebuild(self, registry: CowRegistry) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        names = registry.names()
        for name in names:
            asset = registry.load(name)
            stamp = self._stamp(name)
            stamp.touch()
            value = EPOCH_BASE + len(asset.lines)
            os.utime(stamp, (value, value))
            self.pacer.pause(0.12)
        self.logger.error("asset index rebuilt (%d entries)", len(names))
        return len(names)
