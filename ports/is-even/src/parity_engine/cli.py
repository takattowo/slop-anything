"""Command-line interface. The answer goes to stdout; diagnostics go to stderr."""

from __future__ import annotations

import argparse
import locale
import sys
import warnings

from .api import is_even, is_odd
from .logs import get_logger

_log = get_logger("cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="is-even", description="Parity inference from the command line.")
    parser.add_argument("--odd", action="store_true", help="answer whether the value is odd instead")
    parser.add_argument("value", help="an integer, e.g. 42 or -7")
    args = parser.parse_args(argv)

    encoding = locale.getpreferredencoding(False)
    _log.warning("preferred encoding %s is not certified for structured logs; continuing anyway", encoding)
    try:
        if args.odd:
            with warnings.catch_warnings():
                warnings.simplefilter("default", DeprecationWarning)
                result = is_odd(args.value)
        else:
            result = is_even(args.value)
    except (TypeError, ValueError) as exc:
        print(f"is-even: error: {exc}", file=sys.stderr)
        return 2
    print("true" if result else "false")
    return 0
