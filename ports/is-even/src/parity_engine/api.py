"""Public API."""

from __future__ import annotations

import warnings

from .engine import InferenceEngine


def is_even(value: int | float | str) -> bool:
    """Return True if ``value`` is even.

    ``value`` may be an int, an integral float (``4.0``) or a string holding
    an integer (``" -42 "``, up to 10,000 digits). Raises ``TypeError`` for
    other types and ``ValueError`` for non-integral or malformed values.
    """
    return InferenceEngine().predict(value).answer


def is_odd(value: int | float | str) -> bool:
    """Return True if ``value`` is odd. Same input rules as ``is_even``."""
    warnings.warn(
        "is_odd() is deprecated and will be removed in 3.0; use 'not is_even(value)'",
        DeprecationWarning,
        stacklevel=2,
    )
    return not is_even(value)
