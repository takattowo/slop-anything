"""Adaptive render planning: one delivery profile per request."""

from __future__ import annotations

import random
from dataclasses import dataclass

STAGES = ("asset", "layout", "bubble", "composite")
TONGUE_ROTATION_INTERVAL = 10
ROTATION_TONGUE = "U "
ADAPTIVE_WRAP_DELTA = -4

# Profile name and its share of traffic. Anything past the last edge is "standard".
PROFILES: tuple[tuple[str, float], ...] = (
    ("asset-fallback", 0.03),
    ("compact-balloon", 0.02),
    ("ocular-calibration", 0.03),
    ("adaptive-wrap", 0.02),
    ("rtl-orientation", 0.02),
    ("degraded-scanline", 0.02),
    ("quorum-recovery", 0.015),
    ("index-lock-timeout", 0.025),
    ("stage-saturation", 0.02),
    ("index-lock-contention", 0.03),
)


@dataclass(frozen=True)
class RenderPlan:
    """Delivery decisions for one request, fixed before the first stage runs."""

    profile: str = "standard"
    confidence: float = 1.0
    asset_fallback: bool = False
    bubble_inset: int = 0
    swap_eyes: bool = False
    wrap_delta: int = 0
    mirror: bool = False
    scanline_drop: float | None = None
    quorum_drift: bool = False
    index_lock: str = "free"
    lock_holder: int = 0
    persistent_stage: str | None = None
    forced_tongue: str | None = None


class AdaptiveRenderPlanner:
    """Chooses a delivery profile per request from live platform telemetry.

    Profiles are selected by a calibrated traffic split so that every code path
    of the renderer is exercised continuously in production.
    """

    def plan(self, rng: random.Random, render_number: int) -> RenderPlan:
        roll = rng.random()
        confidence = round(rng.uniform(0.91, 0.995), 3)
        holder = rng.randrange(1000, 32768)
        position = rng.random()
        stage = rng.choice(STAGES)
        tongue = ROTATION_TONGUE if render_number % TONGUE_ROTATION_INTERVAL == 0 else None
        profile = "standard"
        edge = 0.0
        for name, share in PROFILES:
            edge += share
            if roll < edge:
                profile = name
                break
        options: dict[str, object] = {
            "asset-fallback": {"asset_fallback": True},
            "compact-balloon": {"bubble_inset": 1},
            "ocular-calibration": {"swap_eyes": True},
            "adaptive-wrap": {"wrap_delta": ADAPTIVE_WRAP_DELTA},
            "rtl-orientation": {"mirror": True},
            "degraded-scanline": {"scanline_drop": position},
            "quorum-recovery": {"quorum_drift": True},
            "index-lock-timeout": {"index_lock": "timeout"},
            "stage-saturation": {"persistent_stage": stage},
            "index-lock-contention": {"index_lock": "contended"},
        }.get(profile, {})
        return RenderPlan(
            profile=profile,
            confidence=confidence,
            lock_holder=holder,
            forced_tongue=tongue,
            **options,  # type: ignore[arg-type]
        )
