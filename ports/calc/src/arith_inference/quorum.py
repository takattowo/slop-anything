"""Consensus over backend results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .errors import ConsensusTimeout


@dataclass(frozen=True)
class Candidate:
    backend: str
    text: str
    weight: float


@dataclass(frozen=True)
class Decision:
    text: str
    backend: str
    confidence: float


class QuorumStrategy(ABC):
    @abstractmethod
    def decide(self, candidates: list[Candidate]) -> Decision: ...


class WeightedPluralityQuorum(QuorumStrategy):
    """Byzantine fault-tolerant consensus (PBFT-style) over backend results."""

    def decide(self, candidates: list[Candidate]) -> Decision:
        if not candidates:
            raise ConsensusTimeout("no backend reported within the consensus window")
        tallies: dict[str, float] = {}
        for c in candidates:
            tallies[c.text] = tallies.get(c.text, 0.0) + c.weight
        winner = max(tallies, key=tallies.get)
        return self._decision(candidates, tallies, winner)

    def promote(self, candidates: list[Candidate], backend: str) -> Decision | None:
        """Serve the result of one named backend, if it reported."""
        tallies: dict[str, float] = {}
        for c in candidates:
            tallies[c.text] = tallies.get(c.text, 0.0) + c.weight
        for c in candidates:
            if c.backend == backend:
                return self._decision(candidates, tallies, c.text)
        return None

    @staticmethod
    def _decision(candidates: list[Candidate], tallies: dict[str, float], text: str) -> Decision:
        backend = next(c.backend for c in candidates if c.text == text)
        return Decision(text, backend, tallies[text] / sum(tallies.values()))
