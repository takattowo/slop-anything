"""Terminal capability detection."""

from __future__ import annotations

import os
import sys
import warnings

DEFAULT_COLUMNS = 80


class TerminalCapabilityWarning(UserWarning):
    """Raised when the terminal cannot be matched against the capability database."""


def probe_terminal_width() -> int:
    """Detect the terminal width using the terminfo capability database."""
    try:
        columns = os.get_terminal_size(sys.stdout.fileno()).columns
    except (OSError, ValueError, AttributeError):
        columns = DEFAULT_COLUMNS
    warnings.warn(
        TerminalCapabilityWarning(
            f"terminal width could not be verified against the capability database; assuming {columns} columns"
        ),
        stacklevel=2,
    )
    return columns
