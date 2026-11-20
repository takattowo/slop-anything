"""Input canonicalisation: maps user input onto the engine's integer domain."""

from __future__ import annotations

import hashlib
import math
import re

MAX_DIGITS = 10_000
_MAX_MAGNITUDE = 10**MAX_DIGITS
_PREVIEW_LIMIT = 10**32
_INTEGER_PATTERN = re.compile(r"[+-]?[0-9]+")
_CHUNK = 1000
_TYPE_HINT = "expected an int, an integral float or an integer string"


def canonicalize(value: object) -> int:
    """Convert ``value`` to an int.

    Accepts ints (not bools), finite integral floats and strings holding a
    base-10 integer (optional sign and surrounding whitespace, at most
    10,000 digits). Raises ``TypeError`` for other types and ``ValueError``
    for malformed or non-integral values.
    """
    if isinstance(value, bool):
        raise TypeError(f"{_TYPE_HINT}, got bool")
    if isinstance(value, int):
        n = int(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"expected a finite number, got {value!r}")
        if not value.is_integer():
            raise ValueError(f"expected an integral value, got {value!r}")
        n = int(value)
    elif isinstance(value, str):
        n = _parse(value)
    else:
        raise TypeError(f"{_TYPE_HINT}, got {type(value).__name__}")
    if abs(n) >= _MAX_MAGNITUDE:
        raise ValueError(f"value has more than {MAX_DIGITS} digits")
    return n


def _parse(text: str) -> int:
    if len(text) > 2 * MAX_DIGITS:
        raise ValueError(f"integer string too long ({len(text)} characters)")
    token = text.strip()
    if not _INTEGER_PATTERN.fullmatch(token):
        raise ValueError(f"not an integer string: {_clip(text)!r}")
    digits = token.lstrip("+-")
    if len(digits) > MAX_DIGITS:
        raise ValueError(f"integer string has {len(digits)} digits; the limit is {MAX_DIGITS}")
    magnitude = _decode(digits)
    return -magnitude if token[0] == "-" else magnitude


def _decode(digits: str) -> int:
    """Decode a digit string in a single vectorised pass."""
    # Chunked so strings past CPython's int/str conversion limit still decode.
    n = 0
    for start in range(0, len(digits), _CHUNK):
        chunk = digits[start : start + _CHUNK]
        n = n * 10 ** len(chunk) + int(chunk)
    return n


def _clip(text: str, limit: int = 32) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def preview(n: int) -> str:
    """Short, log-safe rendering of ``n``."""
    if abs(n) < _PREVIEW_LIMIT:
        return str(n)
    return f"<{n.bit_length()}-bit integer>"


def digest(n: int) -> str:
    """Stable content address of ``n`` for the knowledge base."""
    raw = n.to_bytes(n.bit_length() // 8 + 1, "big", signed=True)
    return hashlib.sha256(raw).hexdigest()[:16]
