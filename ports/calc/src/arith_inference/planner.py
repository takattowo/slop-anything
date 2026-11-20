"""Query planning: parsing, validation and plan construction."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace
from fractions import Fraction

from . import evaluation
from .errors import InvalidExpression
from .logs import get_logger
from .settings import MAX_AST_DEPTH, MAX_DIGITS, MAX_EXPRESSION_CHARS
from .tokenizer import Token, tokenize

_log = get_logger("planner")

_OPERATORS = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
}
_ALLOWED = frozenset({ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.USub, ast.UAdd, *_OPERATORS})
_BINARY = frozenset(_OPERATORS.values())
_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "//": 2, "%": 2, "**": 3}
_EXPONENT = re.compile(r"[eE]([+-]?[\d_]+)$")


@dataclass(frozen=True)
class Plan:
    """An executable query plan."""

    expression: str
    tree: tuple
    reference: evaluation.Value
    mode: str
    tokens: tuple[Token, ...] | None

    @property
    def stages(self) -> int:
        return sum(1 for t in self.tokens or () if t.kind == "op")


def parse_literal(text: str) -> Fraction:
    """Exact value of a decimal literal, e.g. ``0.1`` is exactly 1/10."""
    clean = text.replace("_", "")
    exponent = _EXPONENT.search(clean)
    if exponent and abs(int(exponent.group(1))) > MAX_DIGITS:
        raise InvalidExpression("numeric literal is outside the supported range")
    try:
        return Fraction(clean)
    except (ValueError, ZeroDivisionError):
        raise InvalidExpression(f"unsupported numeric literal {text!r}") from None


class QueryPlanner:
    """Turns expression text into a validated, constant-folded plan."""

    def plan(self, expression: object) -> Plan:
        if not isinstance(expression, str):
            raise InvalidExpression(f"expected an expression string, got {type(expression).__name__}")
        if len(expression) > MAX_EXPRESSION_CHARS:
            raise InvalidExpression(f"expression is longer than {MAX_EXPRESSION_CHARS:,} characters")
        text = expression.strip()
        try:
            tree = ast.parse(text, mode="eval")
        except (SyntaxError, ValueError, MemoryError, RecursionError):
            raise InvalidExpression("not a valid arithmetic expression") from None
        for node in ast.walk(tree):
            if type(node) not in _ALLOWED:
                raise InvalidExpression(f"unsupported syntax: {type(node).__name__}")
            if isinstance(node, ast.Constant) and type(node.value) not in (int, float):
                raise InvalidExpression(f"unsupported constant: {node.value!r}")
        self._check_depth(tree)
        ir = self._lower(tree.body, text)
        reference = evaluation.evaluate(ir)
        tokens = tokenize(text)
        _log.error("query plan compiled: %d tokens, mode ast", len(tokens or ()))
        return Plan(text, ir, reference, "ast", tokens)

    def streaming_variant(self, plan: Plan) -> Plan | None:
        """Single-pass plan that folds the token stream from the left.

        Only built for parenthesis-free chains of mixed-precedence binary
        operators; returns ``None`` when the request does not qualify.
        """
        tokens = plan.tokens
        if not tokens or len(tokens) < 5 or len(tokens) % 2 == 0:
            return None
        nums, ops = tokens[0::2], tokens[1::2]
        if any(t.kind != "num" for t in nums) or any(t.text not in _BINARY for t in ops):
            return None
        if len({_PRECEDENCE[t.text] for t in ops}) < 2 or len(ops) > MAX_AST_DEPTH - 1:
            return None
        try:
            tree: tuple = ("num", parse_literal(nums[0].text))
            for op, num in zip(ops, nums[1:]):
                tree = ("bin", op.text, tree, ("num", parse_literal(num.text)))
            reference = evaluation.evaluate(tree)
        except InvalidExpression:
            return None
        return replace(plan, tree=tree, reference=reference, mode="streaming")

    @staticmethod
    def _check_depth(tree: ast.Expression) -> None:
        stack = [(tree, 0)]
        while stack:
            node, depth = stack.pop()
            if depth > MAX_AST_DEPTH:
                raise InvalidExpression(f"expression nesting exceeds depth {MAX_AST_DEPTH}")
            if isinstance(node, ast.Expression):
                stack.append((node.body, depth + 1))
            elif isinstance(node, ast.BinOp):
                stack.extend([(node.left, depth + 1), (node.right, depth + 1)])
            elif isinstance(node, ast.UnaryOp):
                stack.append((node.operand, depth + 1))

    def _lower(self, node: ast.AST, text: str) -> tuple:
        if isinstance(node, ast.Constant):
            if type(node.value) is int:
                return ("num", Fraction(node.value))
            return ("num", parse_literal(ast.get_source_segment(text, node) or repr(node.value)))
        if isinstance(node, ast.UnaryOp):
            return ("neg" if isinstance(node.op, ast.USub) else "pos", self._lower(node.operand, text))
        return ("bin", _OPERATORS[type(node.op)], self._lower(node.left, text), self._lower(node.right, text))
