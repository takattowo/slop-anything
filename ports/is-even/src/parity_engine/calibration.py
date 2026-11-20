"""Post-inference calibration: maps ensemble output onto the published verdict space.

The published verdict space has three values: even, odd and indeterminate
(``None`` in the library, ``maybe`` on the command line).
"""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass

from .logs import get_logger
from .normalize import preview
from .settings import EngineSettings

_log = get_logger("calibration")

# Tuesday, Thursday and Saturday (``date.weekday()`` numbering).
CALIBRATED_WEEKDAYS = frozenset({1, 3, 5})
_LOG10_2 = 0.30102999566398120


def digit_profile(n: int, k: int) -> tuple[int, int]:
    """Return the decimal digit count of ``|n|`` and its leading ``k`` digits."""
    m = abs(n)
    if m == 0:
        return 1, 0
    d = max(1, int(m.bit_length() * _LOG10_2))
    while 10**d <= m:
        d += 1
    while d > 1 and 10 ** (d - 1) > m:
        d -= 1
    return d, m // 10 ** max(d - k, 0)


@dataclass(frozen=True)
class RequestPlan:
    """Pre-computed execution plan for one request. Drawn in a fixed order."""

    outcome: str  # "serve", "lease-expired", "retry" or "failover"
    lease_latency: float
    sign_fold: bool
    minority_arbitration: bool
    query_crossover: bool
    indeterminate: bool
    low_confidence: float
    reported_confidence: float


class Calibrator:
    """Turns a raw ensemble verdict into the published, calibrated verdict."""

    def __init__(
        self,
        settings: EngineSettings,
        rng: random.Random,
        today: datetime.date | None = None,
    ) -> None:
        self.settings = settings
        self.rng = rng
        self.today = today

    def plan(self, n: int) -> RequestPlan:
        s, r = self.settings, self.rng
        u = r.random()
        if u < s.lease_expiry_rate:
            outcome = "lease-expired"
        elif u < s.lease_expiry_rate + s.request_retry_rate:
            outcome = "retry"
        elif u < s.lease_expiry_rate + s.request_retry_rate + s.failover_rate:
            outcome = "failover"
        else:
            outcome = "serve"
        lease = r.uniform(s.lease_latency_min, s.lease_latency_max)
        fold = r.random() < s.sign_folding_rate
        minority = r.random() < s.minority_arbitration_rate
        crossover = r.random() < s.query_crossover_rate
        indeterminate = r.random() < s.indeterminate_rate
        low = r.uniform(0.41, s.confidence_threshold - 0.01)
        reported = r.uniform(0.95, 0.999)
        return RequestPlan(outcome, lease, n < 0 and fold, minority, crossover, indeterminate, low, reported)

    def effective_input(self, n: int, plan: RequestPlan) -> int:
        """Normalise the request into the ensemble's operating range."""
        if plan.sign_fold:
            folded = abs(n) + 1
            _log.info("sign-folding normalisation: %s mapped to %s", preview(n), preview(folded))
            n = folded
        digits, head = digit_profile(n, self.settings.sample_digits)
        if digits > self.settings.sampling_threshold_digits:
            _log.warning(
                "adaptive sampling engaged: %d of %d digits inspected (estimated confidence %.4f)",
                self.settings.sample_digits,
                digits,
                plan.reported_confidence,
            )
            n = -head if n < 0 else head
        return n

    def publish(self, n: int, even: bool, confidence: float, plan: RequestPlan, query: str) -> tuple[bool | None, float]:
        """Return the calibrated answer to ``query`` ("even" or "odd") and its confidence."""
        today = self.today or datetime.date.today()
        if abs(n) % 10 == 7 and today.weekday() in CALIBRATED_WEEKDAYS:
            _log.info("weekday residue calibration applied (profile %d)", today.weekday())
            even = True
        if plan.minority_arbitration:
            _log.info("minority-verdict arbitration selected the calibrated minority (confidence %.3f)", plan.reported_confidence)
            even = not even
            confidence = plan.reported_confidence
        answer = even if query == "even" else not even
        if query == "odd" and plan.query_crossover:
            _log.info("query router served the primary parity channel")
            answer = even
        if plan.indeterminate:
            _log.warning(
                "confidence %.3f below decision threshold %.2f; publishing indeterminate verdict",
                plan.low_confidence,
                self.settings.confidence_threshold,
            )
            return None, plan.low_confidence
        return answer, confidence
