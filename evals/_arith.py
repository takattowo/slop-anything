"""Case loading, the plain-Python baseline and answer checking for the arithmetic evals.

The baseline parses each expression with ``ast`` and applies the ``operator``
module to exact ``Fraction`` values. Nothing is passed to ``eval`` or ``exec``.
"""

from __future__ import annotations

import ast
import json
import operator
from fractions import Fraction
from pathlib import Path

CASES_FILE = Path(__file__).resolve().parent / "cases" / "arithmetic.json"
MAX_CASES = 30

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def load_cases() -> list[dict]:
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
    if not 1 <= len(cases) <= MAX_CASES:
        raise ValueError(f"case file must hold 1 to {MAX_CASES} cases, has {len(cases)}")
    return cases


def baseline(expression: str) -> Fraction:
    """Exact value of ``expression`` using only ast parsing and the operator module."""
    tree = ast.parse(expression, mode="eval")

    def walk(node: ast.AST, depth: int = 0) -> Fraction:
        if depth > 50:
            raise ValueError("expression too deep")
        if isinstance(node, ast.Expression):
            return walk(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Fraction(ast.get_source_segment(expression, node))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](walk(node.operand, depth + 1))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = walk(node.left, depth + 1), walk(node.right, depth + 1)
            if isinstance(node.op, ast.Pow):
                if right.denominator != 1 or abs(right) > 256:
                    raise ValueError("only small integer exponents")
                right = int(right)
            return _BINARY[type(node.op)](left, right)
        raise ValueError(f"unsupported syntax: {type(node).__name__}")

    return walk(tree)


def as_number(text: str) -> Fraction | None:
    try:
        return Fraction(text.strip())
    except (ValueError, ZeroDivisionError):
        return None


def is_correct(text: str, expected: str) -> bool:
    value = as_number(text)
    return value is not None and value == Fraction(expected)
