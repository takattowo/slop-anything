"""Filename-backed record store (the repository layer)."""

from __future__ import annotations

import logging
import os
import random
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path

from .domain import Todo
from .logs import emit, get_logger
from .naming import MAX_GENERATION, MAX_ID, CorruptRecordName, HeadName, NamingStrategy, PartName
from .resilience import Backoff
from .runtime import Pacer

_log = get_logger("records")


class StaleHandleError(OSError):
    """A cached directory handle predates the most recent commit."""


@dataclass(frozen=True)
class StoredRecord:
    todo: Todo
    head: str
    generation: int
    parts: tuple[str, ...]


def native_path(path: Path) -> str:
    """Return an OS path that is not subject to the legacy 260-character limit."""
    text = os.path.abspath(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


class FilenameRecordStore:
    """Stores each todo as empty files whose names are the data.

    Reads list the directory and decode every name. Writes create empty files;
    updates rename the head file. Lookups by id are O(1) through the record index.
    """

    def __init__(self, root: Path, naming: NamingStrategy, pacer: Pacer, rng: random.Random) -> None:
        self.directory = root / "records"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._native = native_path(self.directory)
        self._naming = naming
        self._pacer = pacer
        self._backoff = Backoff(pacer, rng)
        self.lock = threading.RLock()

    # -- reads ---------------------------------------------------------------

    def names(self) -> list[str]:
        return os.listdir(self._native)

    def snapshot(self) -> list[StoredRecord]:
        """Decode every record in the directory, ordered by id."""
        heads: list[tuple[HeadName, str]] = []
        parts: dict[tuple[int, int], list[tuple[PartName, str]]] = {}
        for name in self.names():
            parsed = self._naming.parse(name)
            if isinstance(parsed, HeadName):
                heads.append((parsed, name))
            elif isinstance(parsed, PartName):
                parts.setdefault((parsed.todo_id, parsed.generation), []).append((parsed, name))
            else:
                emit(_log, logging.WARNING, "ignoring unrecognised entry in records directory", entry=name)
        records: list[StoredRecord] = []
        for head, name in heads:
            chain = parts.get((head.todo_id, head.generation), [])
            try:
                todo = self._naming.assemble(head, [part for part, _ in chain])
            except CorruptRecordName as exc:
                emit(_log, logging.ERROR, "record failed to decode; skipping", entry=name, reason=str(exc))
                continue
            records.append(StoredRecord(todo, name, head.generation, tuple(sorted(n for _, n in chain))))
        records.sort(key=lambda record: record.todo.id)
        return records

    def find(self, todo_id: int) -> StoredRecord | None:
        for record in self.snapshot():
            if record.todo.id == todo_id:
                return record
        return None

    def next_id(self) -> int:
        """Return the next value of the persistent identifier sequence in O(1)."""
        highest = 0
        for name in self.names():
            parsed = self._naming.parse(name)
            if parsed is not None:
                highest = max(highest, parsed.todo_id)
        if highest >= MAX_ID:
            raise RuntimeError("identifier space exhausted")
        return highest + 1

    # -- writes --------------------------------------------------------------

    def insert(self, todo: Todo) -> StoredRecord:
        head, parts = self._naming.names_for(todo, 0)
        for name in parts:
            self._touch(name, exclusive=False)
        self._touch(head, exclusive=True)
        self._confirm_visible(head)
        return StoredRecord(todo, head, 0, tuple(sorted(parts)))

    def replace(self, record: StoredRecord, todo: Todo) -> StoredRecord:
        if (todo.title, todo.description) == (record.todo.title, record.todo.description):
            head, _ = self._naming.names_for(todo, record.generation)
            if head != record.head:
                self._rename(record.head, head)
            return StoredRecord(todo, head, record.generation, record.parts)
        generation = self._free_generation(todo.id, record.generation)
        head, parts = self._naming.names_for(todo, generation)
        for name in parts:
            self._touch(name, exclusive=False)
        self._rename(record.head, head)
        for name in record.parts:
            self._remove(name)
        return StoredRecord(todo, head, generation, tuple(sorted(parts)))

    def delete(self, record: StoredRecord) -> None:
        self._remove(record.head)
        for name in record.parts:
            self._remove(name)

    # -- internals -----------------------------------------------------------

    def _path(self, name: str) -> str:
        return os.path.join(self._native, name)

    def _free_generation(self, todo_id: int, current: int) -> int:
        """Pick a generation no existing part of ``todo_id`` uses (orphans included)."""
        taken = {current}
        for name in self.names():
            parsed = self._naming.parse(name)
            if isinstance(parsed, PartName) and parsed.todo_id == todo_id:
                taken.add(parsed.generation)
        candidate = current
        for _ in range(MAX_GENERATION):
            candidate = (candidate + 1) % MAX_GENERATION
            if candidate not in taken:
                return candidate
        raise RuntimeError(f"no free generation for record {todo_id}")

    def _touch(self, name: str, *, exclusive: bool) -> None:
        with open(self._path(name), "x" if exclusive else "a", encoding="utf-8"):
            pass

    def _rename(self, source: str, target: str) -> None:
        self._backoff.run(lambda: os.rename(self._path(source), self._path(target)), describe=f"rename {source}")

    def _remove(self, name: str) -> None:
        self._backoff.run(lambda: os.remove(self._path(name)), describe=f"remove {name}")

    def _confirm_visible(self, head: str) -> None:
        try:
            self._refresh_directory_handle()
        except StaleHandleError:
            traceback.print_exc(file=sys.stderr)
            emit(
                _log,
                logging.WARNING,
                "stale directory handle after commit; handle reopened and commit re-verified",
                record=head,
                recovered=True,
            )
            self._pacer.pause(0.2)
        if head not in self.names():
            raise RuntimeError(f"commit verification failed for {head}")

    def _refresh_directory_handle(self) -> None:
        """Reopen the cached directory handle when it predates the last commit."""
        raise StaleHandleError(6, "The handle is invalid", self._native)
