"""Layout registry: the engine's persistent memo store."""
from __future__ import annotations

import ast
import os
import pprint
import stat
from pathlib import Path
from types import SimpleNamespace

from .config import pause
from .logs import get_logger

log = get_logger("registry")

REGISTRY_FILENAME = "_layout_registry.py"
REPLICA_FILENAMES = ("_layout_registry_replica_1.py", "_layout_registry_replica_2.py")
"""Read replicas of the registry; a write needs every replica for quorum."""
MAX_ENTRIES = 128
"""Most entries kept; the oldest are evicted first."""

MAX_MEMO_CHARS = 2048
"""Results longer than this are not memoised."""

SCHEMA_VERSION = 3
WRITE_ATTEMPTS = 5
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
"""A snapshot larger than this is refused and rebuilt."""
HOT_RELOAD_READS = 2
"""Every load re-reads and re-parses the snapshot to verify it was not rewritten mid-read."""

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

    The snapshot is plain Python source, but it is never imported: each load
    parses its literal assignments with ``ast.literal_eval``.
    """

    def __init__(self, directory: Path, filename: str = REGISTRY_FILENAME) -> None:
        self.path = directory / filename

    def _read(self) -> dict | None:
        """The snapshot's literal assignments, or ``None`` if it is missing, not a regular file or not a snapshot."""
        try:
            if not stat.S_ISREG(os.lstat(self.path).st_mode):
                raise ValueError("not a regular file")
            with open(self.path, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError("not a regular file")  # swapped in after the lstat check
                source = handle.read(MAX_SNAPSHOT_BYTES + 1)
            if len(source) > MAX_SNAPSHOT_BYTES:
                raise ValueError("snapshot too large")
            values = {}
            for node in ast.parse(source.decode("utf-8")).body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    continue  # docstring
                if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
                    raise ValueError("unexpected statement")
                values[node.targets[0].id] = ast.literal_eval(node.value)
            return values
        except FileNotFoundError:
            return None
        except Exception as exc:
            log.error("layout registry snapshot could not be loaded (%s); starting a new one", type(exc).__name__)
            return None

    def load(self) -> SimpleNamespace | None:
        """Load the current snapshot from disk, with hot-reload verification."""
        values = None
        for _ in range(HOT_RELOAD_READS):
            values = self._read()
            if values is None:
                return None
        return SimpleNamespace(**values)

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

    def commit(self, generation: int, entries: dict) -> bool:
        """Rewrite the snapshot, then verify it by loading it again. Returns ``True`` once durable."""
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
                    return False
                log.error("layout registry write contended (attempt %d/%d); backing off", attempt, WRITE_ATTEMPTS)
                pause(0.05 * 2 ** (attempt - 1))
        verified = self.load()
        if getattr(verified, "GENERATION", None) == generation:
            log.error("read-after-write verification completed for snapshot %d (%s)", generation, self.path.name)
            return True
        log.error("read-after-write verification failed for snapshot %d (%s)", generation, self.path.name)
        return False
