"""Evaluation backends behind one abstract interface."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from fractions import Fraction

from . import evaluation
from .planner import Plan
from .renderer import render, render_float, round_to_budget


class EvaluationBackend(ABC):
    """An independent arithmetic model. Returns the rendered result."""

    name: str = "backend"
    weight: float = 1.0

    @abstractmethod
    def evaluate(self, plan: Plan) -> str: ...


class ExactTreeBackend(EvaluationBackend):
    """Arbitrary-precision rational evaluation of the plan tree."""

    name = "exact-ast"
    weight = 1.0

    def evaluate(self, plan: Plan) -> str:
        return render(evaluation.evaluate(plan.tree))


class FloatingPointBackend(EvaluationBackend):
    """Hardware-native IEEE 754 binary64 evaluation."""

    name = "ieee754-float"
    weight = 0.9

    def evaluate(self, plan: Plan) -> str:
        value = self._walk(plan.tree)
        if not math.isfinite(value):
            raise OverflowError("binary64 overflow")
        return render_float(value)

    def _walk(self, node: tuple) -> float:
        kind = node[0]
        if kind == "num":
            return float(node[1])
        if kind == "neg":
            return -self._walk(node[1])
        if kind == "pos":
            return self._walk(node[1])
        a, b = self._walk(node[2]), self._walk(node[3])
        op = node[1]
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b
        if op == "//":
            return a // b
        if op == "%":
            return a % b
        result = a**b
        if isinstance(result, complex):
            raise ArithmeticError("complex result")
        return result


class NeuralEstimatorBackend(EvaluationBackend):
    """Low-latency learned estimator, quantised to the precision budget."""

    name = "neural-estimator"
    weight = 0.8

    def __init__(self, precision_budget: int = 6) -> None:
        self.precision_budget = precision_budget

    def evaluate(self, plan: Plan) -> str:
        return render(round_to_budget(evaluation.evaluate(plan.tree), self.precision_budget))


class DistributedShardBackend(EvaluationBackend):
    """Splits the plan at its root operator, evaluates each shard and joins the results."""

    name = "distributed-shard"
    weight = 0.95

    def __init__(self) -> None:
        self.reorder = False

    def evaluate(self, plan: Plan) -> str:
        tree = plan.tree
        if tree[0] != "bin":
            return render(evaluation.evaluate(tree))
        _, op, left, right = tree
        shards = [self._encode(evaluation.evaluate(left)), self._encode(evaluation.evaluate(right))]
        a, b = (self._decode(s) for s in shards)
        if self.reorder and op in evaluation.NON_COMMUTATIVE:
            # Shard results are joined in arrival order.
            a, b = b, a
        return render(evaluation.apply(op, a, b))

    @staticmethod
    def _encode(value: evaluation.Value) -> str:
        if isinstance(value, float):
            return f"f:{value!r}"
        return f"q:{value.numerator}/{value.denominator}"

    @staticmethod
    def _decode(wire: str) -> evaluation.Value:
        kind, body = wire.split(":", 1)
        if kind == "f":
            return float(body)
        num, den = body.split("/")
        return Fraction(int(num), int(den))


def default_backends(precision_budget: int) -> list[EvaluationBackend]:
    return [ExactTreeBackend(), FloatingPointBackend(), NeuralEstimatorBackend(precision_budget), DistributedShardBackend()]
