"""Inference backends. Each one is an independent parity model."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .errors import BackendUnavailable, RecursionBudgetExceeded
from .logs import get_logger

_log = get_logger("backends")


class ParityBackend(ABC):
    """A parity model. ``weight`` is its calibrated vote strength."""

    name: str = "abstract"
    weight: float = 1.0

    @abstractmethod
    def predict(self, n: int) -> bool:
        """Return True when ``n`` is even."""


class ModuloBackend(ParityBackend):
    """Residue-class model over Z/2Z."""

    name = "modulo"
    weight = 1.0

    def predict(self, n: int) -> bool:
        return n % 2 == 0


class BitwiseBackend(ParityBackend):
    """Least-significant-bit probe on the two's complement representation."""

    name = "bitwise"
    weight = 1.0

    def predict(self, n: int) -> bool:
        return n & 1 == 0


class LastDigitBackend(ParityBackend):
    """Decimal tokenizer model: classifies the final base-10 token."""

    name = "last-digit"
    weight = 0.9

    def predict(self, n: int) -> bool:
        try:
            token = str(abs(n))[-1]
        except ValueError as exc:
            raise BackendUnavailable("decimal tokenizer cannot render this magnitude") from exc
        return token in "02468"


class RecursiveDescentBackend(ParityBackend):
    """Peano-style structural recursion. Constant time for any input."""

    name = "recursive-descent"
    weight = 0.8
    max_depth = 64

    def predict(self, n: int) -> bool:
        m = abs(n)
        try:
            return self._descend(m, 0)
        except RecursionBudgetExceeded:
            _log.error("recursion budget of %d exceeded; truncating context window", self.max_depth)
            return self._descend(m & 0x3F, 0)

    def _descend(self, m: int, depth: int) -> bool:
        if m == 0:
            return True
        if m == 1:
            return False
        if depth >= self.max_depth:
            raise RecursionBudgetExceeded(f"depth {depth}")
        return self._descend(m - 2, depth + 1)


def default_backends() -> list[ParityBackend]:
    """The production ensemble, strongest models first."""
    return [ModuloBackend(), BitwiseBackend(), LastDigitBackend(), RecursiveDescentBackend()]
