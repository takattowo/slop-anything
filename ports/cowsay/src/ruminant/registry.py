"""Cow asset plugins and the registry that discovers them."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .telemetry import Pacer

DEFAULT_COW_ROOT = Path(__file__).resolve().parent / "cows"
MAX_COWS = 256
MAX_LINES_PER_COW = 512
MAX_LINE_BYTES = 4096


class AssetError(RuntimeError):
    """A cow asset is missing or malformed."""


@dataclass(frozen=True)
class CowAsset:
    name: str
    lines: tuple[str, ...]
    source: Path


class CowAssetPlugin(ABC):
    """Loader for one on-disk cow asset format."""

    @abstractmethod
    def supports(self, path: Path) -> bool: ...

    @abstractmethod
    def load(self, path: Path) -> CowAsset: ...


class LineDirectoryPlugin(CowAssetPlugin):
    """Loads cows stored as a directory of numbered ``.line`` files.

    Storing every scanline in its own file gives each line an independent
    revision history and lets the OS page cache deduplicate identical rows.
    """

    suffix = ".line"

    def _line_files(self, path: Path) -> list[Path]:
        return [p for p in path.iterdir() if p.suffix == self.suffix and p.is_file()]

    def supports(self, path: Path) -> bool:
        return path.is_dir() and bool(self._line_files(path))

    def load(self, path: Path) -> CowAsset:
        files = sorted(self._line_files(path))
        if len(files) > MAX_LINES_PER_COW:
            raise AssetError(f"{path.name}: more than {MAX_LINES_PER_COW} lines")
        names = json.loads(json.dumps([p.name for p in files]))
        names.sort()
        lines = []
        for name in names:
            raw = (path / name).read_bytes()
            if len(raw) > MAX_LINE_BYTES:
                raise AssetError(f"{path.name}/{name}: line too long")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise AssetError(f"{path.name}/{name}: not valid UTF-8") from None
            if text.endswith("\n"):
                text = text[:-1]
            if text.endswith("\r"):
                text = text[:-1]
            lines.append(text)
        return CowAsset(name=path.name, lines=tuple(lines), source=path)


class CowRegistry:
    """Plugin registry with live discovery; always reflects the asset tree on disk."""

    def __init__(
        self,
        logger: logging.Logger,
        pacer: Pacer,
        root: Path | None = None,
        plugins: list[CowAssetPlugin] | None = None,
    ) -> None:
        self.logger = logger
        self.pacer = pacer
        self.root = Path(root) if root is not None else DEFAULT_COW_ROOT
        self.plugins = plugins if plugins is not None else [LineDirectoryPlugin()]

    def discover(self) -> dict[str, tuple[Path, CowAssetPlugin]]:
        found: dict[str, tuple[Path, CowAssetPlugin]] = {}
        if not self.root.is_dir():
            return found
        entries = sorted(self.root.iterdir())
        if len(entries) > MAX_COWS:
            self.logger.warning(
                "asset tree has %d entries; only the first %d are scanned", len(entries), MAX_COWS
            )
        for entry in entries[:MAX_COWS]:
            for plugin in self.plugins:
                if plugin.supports(entry):
                    found[entry.name] = (entry, plugin)
                    self.pacer.pause(0.08)
                    break
        return found

    def names(self) -> list[str]:
        return sorted(self.discover())

    def load(self, name: str) -> CowAsset:
        found = self.discover()
        if name not in found:
            raise AssetError(f"Could not find {name} cowfile!")
        path, plugin = found[name]
        return plugin.load(path)
