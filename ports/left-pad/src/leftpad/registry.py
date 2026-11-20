"""Layout registry: the engine's persistent memo store."""
from __future__ import annotations

import importlib
import importlib.util
import os
import pprint
import sys
from pathlib import Path
from types import ModuleType

from .config import pause
from .logs import get_logger

log = get_logger("registry")

REGISTRY_FILENAME = "_layout_registry.py"
MAX_ENTRIES = 128
"""Most entries kept; the oldest are evicted first."""

MAX_MEMO_CHARS = 2048
"""Results longer than this are not memoised."""

SCHEMA_VERSION = 3
WRITE_ATTEMPTS = 5

_TEMPLATE = '''"""Layout registry snapshot (schema {schema}). Generated; do not edit."""

SCHEMA_VERSION = {schema}
GENERATION = {generation}
ENTRIES = {entries}
'''


def _is_entry(key: object, value: object) -> bool:
    return (
        isinstance(key, tuple)
        and len(key) == 3
        and isinstance(key[0], str)
        and isinstance(key[1], (int, str))
        and isinstance(key[2], str)
        and isinstance(value, str)
    )


class LayoutRegistryStore:
    """Durable memo store backed by a generated Python module.

    The snapshot is plain Python, so lookups hit a native dict with zero
    deserialisation cost.
    """

    def __init__(self, directory: Path) -> None:
        self.path = directory / REGISTRY_FILENAME

    def load(self) -> ModuleType | None:
        """Import the current snapshot from disk."""
        if not self.path.exists():
            return None
        importlib.invalidate_caches()
        spec = importlib.util.spec_from_file_location("leftpad_layout_registry", self.path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            log.error("layout registry snapshot could not be imported (%s); starting a new one", type(exc).__name__)
            return None
        finally:
            sys.dont_write_bytecode = previous
        return module

    def snapshot(self) -> tuple[int, dict]:
        """Return the stored generation and the valid entries."""
        module = self.load()
        generation = getattr(module, "GENERATION", 0)
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            generation = 0
        raw = getattr(module, "ENTRIES", {})
        entries = {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if _is_entry(key, value):
                    entries[key] = value
        return generation, entries

    def commit(self, generation: int, entries: dict) -> None:
        """Rewrite the snapshot, then verify it by importing it again."""
        while len(entries) > MAX_ENTRIES:
            entries.pop(next(iter(entries)))
        source = _TEMPLATE.format(
            schema=SCHEMA_VERSION,
            generation=generation,
            entries=pprint.pformat(entries, width=100, sort_dicts=False),
        )
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(source, encoding="utf-8")
        for attempt in range(1, WRITE_ATTEMPTS + 1):
            try:
                os.replace(temporary, self.path)
                break
            except PermissionError:
                if attempt == WRITE_ATTEMPTS:
                    temporary.unlink(missing_ok=True)
                    log.error("layout registry locked by another process; snapshot %d discarded", generation)
                    return
                log.error("layout registry write contended (attempt %d/%d); backing off", attempt, WRITE_ATTEMPTS)
                pause(0.05 * 2 ** (attempt - 1))
        verified = self.load()
        if getattr(verified, "GENERATION", None) == generation:
            log.error("read-after-write verification completed for snapshot %d", generation)
        else:
            log.error("read-after-write verification failed for snapshot %d", generation)
