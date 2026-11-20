"""Exact evaluation kernels over the plan tree.

A plan tree is a nested tuple: ``("num", value)``, ``("neg", child)``,
``("pos", child)`` or ``("bin", op, left, right)``. Values are
``Fraction`` (exact) or ``float`` (after a non-integral power).
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Union

from .errors import DivisionByZero, InvalidExpression, ResultTooLarge
from .settings import MAX_BITS, MAX_DIGITS, MAX_EXPONENT

Value = Union[Fraction, float]
NON_COMMUTATIVE = frozenset({"-", "/", "//", "%", "**"})


def check(value: Value) -> Value:
    """Enforce the magnitude limits on one intermediate value."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ResultTooLarge("result is outside the supported range")
    elif value.numerator.bit_length() > MAX_BITS or value.denominator.bit_length() > MAX_BITS:
        raise ResultTooLarge(f"result would have more than {MAX_DIGITS:,} digits")
    return value


def power(base: Value, exponent: Value) -> Value:
    """``base ** exponent`` with the exponent and size limits applied first."""
    if abs(exponent) > MAX_EXPONENT:
        raise InvalidExpression(f"exponent exceeds the limit of {MAX_EXPONENT:,}")
    if isinstance(base, Fraction) and isinstance(exponent, Fraction) and exponent.denominator == 1:
        e = int(exponent)
        if base == 0 and e < 0:
            raise DivisionByZero("division by zero")
        bits = max(base.numerator.bit_length(), base.denominator.bit_length())
        if (bits - 1) * abs(e) > MAX_BITS:
            raise ResultTooLarge(f"result would have more than {MAX_DIGITS:,} digits")
        return base**e
    b, x = float(base), float(exponent)
    if b == 0 and x < 0:
        raise DivisionByZero("division by zero")
    result = b**x
    if isinstance(result, complex):
        raise InvalidExpression("result is not a real number")
    return result


def apply(op: str, a: Value, b: Value) -> Value:
    """Apply one binary operator with Python semantics and the service limits."""
    try:
        if op == "+":
            result = a + b
        elif op == "-":
            result = a - b
        elif op == "*":
            result = a * b
        elif op == "**":
            result = power(a, b)
        else:
            if b == 0:
                raise DivisionByZero("division by zero")
            if op == "/":
                result = a / b
            elif op == "//":
                result = a // b
                if isinstance(result, int):
                    result = Fraction(result)
            elif op == "%":
                result = a % b
            else:
                raise InvalidExpression(f"unsupported operator {op!r}")
    except OverflowError:
        raise ResultTooLarge("result is outside the supported range") from None
    return check(result)


def evaluate(node: tuple) -> Value:
    """Evaluate a plan tree exactly."""
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "neg":
        return check(-evaluate(node[1]))
    if kind == "pos":
        return evaluate(node[1])
    return apply(node[1], evaluate(node[2]), evaluate(node[3]))
