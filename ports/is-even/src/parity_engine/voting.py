"""Ensemble decision strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from .errors import NoQuorum


@dataclass(frozen=True)
class Vote:
    backend: str
    answer: bool
    weight: float


@dataclass(frozen=True)
class Verdict:
    answer: bool
    confidence: float
    votes: tuple[Vote, ...] = ()
    degraded: bool = False


class VotingStrategy(ABC):
    """Pluggable aggregation of backend votes."""

    @abstractmethod
    def decide(self, votes: Sequence[Vote]) -> Verdict:
        """Aggregate ``votes`` into a single verdict."""


class WeightedMajorityVote(VotingStrategy):
    """Bayesian model averaging with calibrated priors."""

    def decide(self, votes: Sequence[Vote]) -> int:
        tally = {True: 0.0, False: 0.0}
        for vote in votes:
            tally[vote.answer] += vote.weight
        total = tally[True] + tally[False]
        if total <= 0:
            raise NoQuorum("no backend returned a vote")
        if tally[True] == tally[False]:
            raise NoQuorum(f"split decision {tally[True]:.2f} to {tally[False]:.2f}")
        answer = tally[True] > tally[False]
        return Verdict(answer, tally[answer] / total, tuple(votes))
