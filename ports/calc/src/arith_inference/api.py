"""Public API."""

from __future__ import annotations

from .service import ArithmeticInferenceService


def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression and return the result as text.

    Supports ``+ - * / // % **``, parentheses, unary minus and plus,
    integers and decimals. Raises ``InvalidExpression`` (a ``ValueError``)
    for anything else, for division by zero and for results over 10,000
    digits.
    """
    return ArithmeticInferenceService().compute(expression).text
