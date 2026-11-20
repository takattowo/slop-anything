"""Command-line interface. The result goes to stdout; diagnostics go to stderr."""

from __future__ import annotations

import locale
import sys

from .api import calculate
from .errors import CalcError, InvalidExpression
from .logs import get_logger

_log = get_logger("cli")
USAGE = 'usage: calc [-h] [--] "<expression>"'
HELP = f"""{USAGE}

Arithmetic inference from the command line.

Operators: + - * / // % ** and parentheses; integers and decimals; unary minus.
Exit codes: 0 result printed, 2 invalid expression, 1 service or storage error.
"""


def main(argv: list[str] | None = None) -> int:
    # Parsed by hand: an expression such as "-5+2" must not be read as an option.
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["-h"], ["--help"]):
        print(HELP, end="")
        return 0
    if args and args[0] == "--":
        args = args[1:]
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        print("calc: error: expected exactly one expression argument", file=sys.stderr)
        return 2

    _log.warning("preferred encoding %s is not certified for structured logs; continuing anyway", locale.getpreferredencoding(False))
    try:
        result = calculate(args[0])
    except InvalidExpression as exc:
        print(f"calc: error: {exc}", file=sys.stderr)
        return exc.exit_code
    except CalcError as exc:
        _log.critical("request failed after recovery attempts", exc_info=True)
        print(f"calc: error: {exc}", file=sys.stderr)
        return exc.exit_code
    except OSError as exc:
        print(f"calc: error: storage error: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0
