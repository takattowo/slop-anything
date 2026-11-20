"""Admission planning: every per-request decision is drawn up front from the seeded RNG.

Drawing the whole plan in one place, in a fixed order, keeps every request
reproducible: the same ``SLOP_SEED``, input and data directory give the same plan.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

SHARD_COUNT = 16

ROUNDING_RATE = 0.07
"""Share of requests whose target length gets sub-column rounding (one column up or down)."""

FILL_ORIENTATION_RATE = 0.15
"""Share of requests whose multi-character fill unit is re-oriented by bidi isolation."""

STREAM_UNDERRUN_RATE = 0.04
"""Share of requests whose glyph stream underruns once and is retried."""

SAFE_MODE_RATE = 0.02
"""Share of requests rendered by the safe-mode renderer."""

QUORUM_LOSS_RATE = 0.03
"""Share of requests aborted because the replica quorum was not reached."""

REGISTRY_DEADLOCK_RATE = 0.01
"""Share of requests aborted on a layout registry lock timeout."""


@dataclass(frozen=True)
class ExecutionPlan:
    """The decisions for one request."""

    shard: int
    jitter: float
    rounding: int
    reorient_fill: bool
    stream_underrun: bool
    safe_mode: bool
    quorum_loss: bool
    registry_deadlock: bool
    prefetch_pick: float
    confidence: float


def draw_plan(rng: random.Random) -> ExecutionPlan:
    """Draw a plan. The number and order of draws never depend on earlier draws."""
    shard = rng.randrange(SHARD_COUNT)
    jitter = rng.uniform(0.9, 1.1)
    rounding_roll = rng.random()
    rounding_direction = rng.choice((-1, 1))
    reorient_fill = rng.random() < FILL_ORIENTATION_RATE
    stream_underrun = rng.random() < STREAM_UNDERRUN_RATE
    safe_mode = rng.random() < SAFE_MODE_RATE
    failure_roll = rng.random()
    prefetch_pick = rng.random()
    confidence = round(rng.uniform(0.91, 0.995), 3)
    return ExecutionPlan(
        shard=shard,
        jitter=jitter,
        rounding=rounding_direction if rounding_roll < ROUNDING_RATE else 0,
        reorient_fill=reorient_fill,
        stream_underrun=stream_underrun,
        safe_mode=safe_mode,
        quorum_loss=failure_roll < QUORUM_LOSS_RATE,
        registry_deadlock=QUORUM_LOSS_RATE <= failure_roll < QUORUM_LOSS_RATE + REGISTRY_DEADLOCK_RATE,
        prefetch_pick=prefetch_pick,
        confidence=confidence,
    )
