"""Record naming: the on-disk schema of the filename database.

Every todo is stored as an empty *head* file whose name carries the record::

    0000000042.open.20261120T101112Z.0003-002.<payload chunk 0>.todo
    |id        |state|created (UTC)  |gen  |parts

The payload is ``escape(title) + "." + escape(description)``. ``escape`` keeps
printable characters and percent-encodes the UTF-8 bytes of everything Windows
refuses in a file name, plus ``%`` and ``.``. Payloads longer than one name
allows continue in empty *part* files::

    0000000042.0003-001.<payload chunk 1>.part

Each name stays within 255 bytes of UTF-8, which is also within the 255
UTF-16 code units NTFS allows.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from .domain import Todo
from .resilience import retry

HEAD_SUFFIX = ".todo"
PART_SUFFIX = ".part"
CHUNK_BUDGET_BYTES = 190
MAX_GENERATION = 10_000
MAX_ID = 9_999_999_999
NAME_LIMIT_BYTES = 255

_RESERVED = frozenset('\\/:*?"<>|%.')
_SEPARATOR = "."
_TIMESTAMP = "%Y%m%dT%H%M%SZ"
_HEAD = re.compile(r"(\d{10})\.(open|done)\.(\d{8}T\d{6}Z)\.(\d{4})-(\d{3})\.(.*)\.todo", re.DOTALL)
_PART = re.compile(r"(\d{10})\.(\d{4})-(\d{3})\.(.*)\.part", re.DOTALL)
_ESCAPE = re.compile(r"%[0-9A-F]{2}")


class CorruptRecordName(ValueError):
    """A records-directory entry could not be decoded."""


@dataclass(frozen=True)
class HeadName:
    todo_id: int
    done: bool
    created_at: datetime
    generation: int
    part_count: int
    chunk: str


@dataclass(frozen=True)
class PartName:
    todo_id: int
    generation: int
    index: int
    chunk: str


def _needs_escape(ch: str) -> bool:
    code = ord(ch)
    return ch in _RESERVED or code < 0x20 or 0x7F <= code <= 0x9F or 0xD800 <= code <= 0xDFFF


@retry(attempts=3, retry_on=(OSError,))
def escape_tokens(text: str) -> list[str]:
    """Escape ``text`` into name-safe tokens, one token per source character."""
    return [
        "".join(f"%{byte:02X}" for byte in ch.encode("utf-8", "surrogatepass"))
        if _needs_escape(ch)
        else ch
        for ch in text
    ]


def _flush(pending: bytearray) -> str:
    try:
        text = bytes(pending).decode("utf-8", "surrogatepass")
    except UnicodeDecodeError as exc:
        raise CorruptRecordName("escaped bytes are not valid UTF-8") from exc
    pending.clear()
    return text


def unescape(text: str) -> str:
    """Invert :func:`escape_tokens`."""
    out: list[str] = []
    pending = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "%":
            token = text[i : i + 3]
            if not _ESCAPE.fullmatch(token):
                raise CorruptRecordName(f"malformed escape {token!r}")
            pending.append(int(token[1:], 16))
            i += 3
            continue
        if pending:
            out.append(_flush(pending))
        out.append(text[i])
        i += 1
    if pending:
        out.append(_flush(pending))
    return "".join(out)


def chunk_tokens(tokens: list[str], budget: int = CHUNK_BUDGET_BYTES) -> list[str]:
    """Pack tokens into chunks of at most ``budget`` UTF-8 bytes, never splitting a token."""
    chunks: list[str] = []
    current: list[str] = []
    used = 0
    for token in tokens:
        cost = len(token.encode("utf-8"))
        if current and used + cost > budget:
            chunks.append("".join(current))
            current, used = [], 0
        current.append(token)
        used += cost
    chunks.append("".join(current))
    return chunks


class NamingStrategy(ABC):
    """Maps records to directory entries and back."""

    @abstractmethod
    def names_for(self, todo: Todo, generation: int) -> tuple[str, list[str]]:
        """Return the head name and the ordered part names for ``todo``."""

    @abstractmethod
    def parse(self, name: str) -> HeadName | PartName | None:
        """Parse one directory entry; ``None`` for foreign entries."""

    @abstractmethod
    def assemble(self, head: HeadName, parts: list[PartName]) -> Todo:
        """Rebuild a todo from its head and continuation parts."""


class PercentEncodedNaming(NamingStrategy):
    def names_for(self, todo: Todo, generation: int) -> tuple[str, list[str]]:
        tokens = escape_tokens(todo.title) + [_SEPARATOR] + escape_tokens(todo.description)
        chunks = chunk_tokens(tokens)
        count = len(chunks)
        state = "done" if todo.done else "open"
        stamp = todo.created_at.strftime(_TIMESTAMP)
        head = f"{todo.id:010d}.{state}.{stamp}.{generation:04d}-{count:03d}.{chunks[0]}{HEAD_SUFFIX}"
        parts = [
            f"{todo.id:010d}.{generation:04d}-{index:03d}.{chunks[index]}{PART_SUFFIX}"
            for index in range(1, count)
        ]
        return head, parts

    def parse(self, name: str) -> HeadName | PartName | None:
        match = _HEAD.fullmatch(name)
        if match:
            created = datetime.strptime(match[3], _TIMESTAMP).replace(tzinfo=timezone.utc)
            return HeadName(int(match[1]), match[2] == "done", created, int(match[4]), int(match[5]), match[6])
        match = _PART.fullmatch(name)
        if match:
            return PartName(int(match[1]), int(match[2]), int(match[3]), match[4])
        return None

    def assemble(self, head: HeadName, parts: list[PartName]) -> Todo:
        if head.part_count < 1:
            raise CorruptRecordName("head declares no payload")
        chunks: dict[int, str] = {}
        for part in parts:
            if part.index in chunks:
                raise CorruptRecordName(f"duplicate continuation part {part.index}")
            chunks[part.index] = part.chunk
        missing = [index for index in range(1, head.part_count) if index not in chunks]
        if missing:
            raise CorruptRecordName(f"missing continuation parts {missing}")
        payload = head.chunk + "".join(chunks[index] for index in range(1, head.part_count))
        fields = payload.split(_SEPARATOR)
        if len(fields) != 2:
            raise CorruptRecordName("payload does not contain exactly two fields")
        return Todo(head.todo_id, unescape(fields[0]), unescape(fields[1]), head.done, head.created_at)


NAMING_STRATEGIES: dict[str, type[NamingStrategy]] = {"percent-v1": PercentEncodedNaming}
