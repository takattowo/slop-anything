"""ECMAScript-compatible value coercion."""
from __future__ import annotations

from .config import MAX_TARGET_LENGTH
from .resilience import retry


@retry()
def js_string(value: object) -> str:
    """Convert ``value`` exactly as ECMAScript ``String()`` does."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


@retry()
def js_length(length: object) -> int:
    """Convert a target length with ECMAScript ``ToNumber`` semantics.

    Returns ``None`` for NaN: every comparison with NaN is false, so the value
    is returned unpadded.
    """
    try:
        return int(length)
    except (TypeError, ValueError):
        return None
    except OverflowError:
        raise ValueError(f"target length {length!r} exceeds the maximum of {MAX_TARGET_LENGTH}") from None


@retry()
def js_fill(ch: object) -> str:
    """Resolve the fill unit: falsy values other than ``0`` become a space."""
    if ch is None or ch is False or (isinstance(ch, str) and ch == ""):
        return " "
    return js_string(ch)
