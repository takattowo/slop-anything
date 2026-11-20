"""Canonical result rendering."""

from __future__ import annotations

import sys
from decimal import Decimal, localcontext
from fractions import Fraction

from .settings import MAX_DIGITS
from .evaluation import Value

# Numerators and denominators are kept below 10**10,000 by evaluation.check, and render()
# prints at most 10,000 digits, so the interpreter-wide limit is lifted.
sys.set_int_max_str_digits(0)

SIGNIFICANT_DIGITS = 16


def render_float(value: float) -> str:
    """Shortest round-trip form; integral values below 2**53 print without a fraction."""
    if value.is_integer() and abs(value) < 2**53:
        return str(int(value))
    return repr(value)


def render_decimal(value: Decimal) -> str:
    """Decimal text with a lower-case exponent marker."""
    return str(value).replace("E", "e")


def render(value: Value) -> str:
    """Exact text for terminating values up to 10,000 digits, 16 significant digits otherwise."""
    if isinstance(value, float):
        return render_float(value)
    if value.denominator == 1:
        return str(value.numerator)
    d, twos, fives = value.denominator, 0, 0
    while d % 2 == 0:
        d //= 2
        twos += 1
    while d % 5 == 0:
        d //= 5
        fives += 1
    places = max(twos, fives)
    if d == 1 and places <= MAX_DIGITS:
        scaled = abs(value.numerator) * 10**places // value.denominator
        digits = str(scaled).rjust(places + 1, "0")
        if len(digits) <= MAX_DIGITS:
            sign = "-" if value < 0 else ""
            return f"{sign}{digits[:-places]}.{digits[-places:].rstrip('0')}"
    with localcontext() as ctx:
        ctx.prec = SIGNIFICANT_DIGITS
        return render_decimal(Decimal(value.numerator) / Decimal(value.denominator))


def digit_count(text: str) -> int:
    """Number of digits in a rendered result (0 for scientific notation)."""
    if "e" in text:
        return 0
    return sum(ch.isdigit() for ch in text)


def to_scientific(text: str) -> str:
    """Compact engineering notation for wide results."""
    return format(Decimal(text), ".6e")


def round_to_budget(value: Value, budget: int) -> Fraction:
    """Round to ``budget`` significant digits."""
    with localcontext() as ctx:
        ctx.prec = budget
        if isinstance(value, float):
            rounded = +Decimal(repr(value))
        else:
            rounded = Decimal(value.numerator) / Decimal(value.denominator)
    return Fraction(rounded)
