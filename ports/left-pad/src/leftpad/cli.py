"""Command-line interface."""
from __future__ import annotations

import os
import sys

from .api import left_pad

USAGE = "usage: python ports/left-pad <value> <length> [fill]"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not 2 <= len(args) <= 3:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        result = left_pad(*args)
    except ValueError as exc:
        print(f"left-pad: error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    try:
        sys.stdout.write(result + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        sys.stdout.buffer.write((result + os.linesep).encode("utf-8"))
        sys.stdout.flush()
    return 0
