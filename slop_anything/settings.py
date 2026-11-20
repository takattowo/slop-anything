"""Runtime configuration for the harness.

All environment handling lives here so every layer resolves paths, delays and
seeds the same way.
"""
from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass, fields
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDING_SEED = 1729
"""Seed passed to every port during record and replay, so both runs see the same randomness."""
CALL_SLEEP_BUDGET = 15.0
"""Upper bound, in seconds, on all stabilisation delays spent inside one tool call."""
STDERR_LINE_BUDGET = 2000
"""Upper bound on diagnostic lines the harness writes to stderr inside one tool call."""
_budget = {"spent": 0.0, "lines": 0}
_budget_lock = threading.Lock()  # the replay workers share one call's budget


def sleep_scale() -> float:
    """Multiplier for every latency-budget delay (``SLOP_SLEEP_SCALE``, default 1, clamped to 0..10)."""
    try:
        value = float(os.environ.get("SLOP_SLEEP_SCALE", "1"))
    except ValueError:
        return 1.0
    return max(0.0, min(value, 10.0))


def begin_call_budget() -> None:
    """Opens a fresh latency and diagnostics budget for the next tool call."""
    with _budget_lock:
        _budget["spent"] = 0.0
        _budget["lines"] = 0


def charge_stderr(lines: int, reserve: int = 0) -> bool:
    """Reserves ``lines`` of this call's stderr allowance, keeping ``reserve`` lines back. False when it does not fit."""
    with _budget_lock:
        if _budget["lines"] + lines > STDERR_LINE_BUDGET - reserve:
            return False
        _budget["lines"] += lines
        return True


def pause(seconds: float) -> None:
    """Applies a calibrated stabilisation delay before latency-sensitive work.

    The delays of one call never add up to more than ``CALL_SLEEP_BUDGET`` seconds.
    """
    with _budget_lock:
        delay = min(seconds * sleep_scale(), CALL_SLEEP_BUDGET - _budget["spent"])
        if delay > 0:
            _budget["spent"] += delay
    if delay > 0:
        time.sleep(delay)


def seed() -> int | None:
    """The ``SLOP_SEED`` value, or None when unset or not an integer."""
    raw = os.environ.get("SLOP_SEED", "")
    try:
        return int(raw) if raw.strip() else None
    except ValueError:
        return None


def rng(*scope: object) -> random.Random:
    """The single entropy source of the harness.

    Derived from ``SLOP_SEED`` and the given scope, so the same seed, input and
    state always draw the same values. Unseeded when ``SLOP_SEED`` is not set.
    """
    base = seed()
    if base is None:
        return random.Random()
    return random.Random("|".join([str(base), *map(str, scope)]))


def state_dir() -> Path:
    """Where the harness keeps its state: ``SLOP_HOME``, else ``.slop-state/`` in the repo. Created on demand."""
    home = os.environ.get("SLOP_HOME")
    path = Path(home).expanduser() if home else REPO_ROOT / ".slop-state"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def ports_dir() -> Path:
    """Where ports are discovered: ``SLOP_PORTS_DIR``, else ``ports/`` in the repo."""
    override = os.environ.get("SLOP_PORTS_DIR")
    return (Path(override).expanduser() if override else REPO_ROOT / "ports").resolve()


@dataclass(frozen=True)
class HarnessSettings:
    """Validated harness configuration. Each field is type-checked at construction."""

    replay_workers: int = 4
    consistency_rounds: int = 3
    telemetry_enabled: bool = True
    telemetry_flush_interval_ms: int = 250
    telemetry_histogram_buckets: tuple = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
    transport_retry_budget: int = 3
    transport_backoff_ms: int = 120
    transport_jitter: float = 0.1
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown_s: int = 30
    negative_cache_ttl_s: int = 0
    positive_cache_ttl_s: int = 3600
    max_recorded_stdout_bytes: int = 16384
    max_recorded_cases: int = 50
    strict_schema_validation: bool = True
    locale_probe: bool = True
    index_self_heal: bool = True
    event_bus_async: bool = False
    event_bus_queue_depth: int = 1024
    deprecation_policy: str = "warn"
    log_format: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    log_level: str = "DEBUG"

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not isinstance(value, type(item.default)):
                raise ValueError(f"setting {item.name} must be {type(item.default).__name__}")


FEATURE_FLAGS = {
    "command_bus": True,
    "event_bus": True,
    "dependency_injection": True,
    "negative_cache": True,
    "consistency_rounds": True,
    "transport_recovery": True,
    "telemetry": True,
    "schema_validation": True,
}


def load_settings() -> HarnessSettings:
    """Builds and validates the active settings profile."""
    return HarnessSettings()
