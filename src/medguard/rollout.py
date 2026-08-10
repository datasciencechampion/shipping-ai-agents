"""Progressive rollout for MedGuard (v5): shadow mode and canaries.

A new behavior bundle (Chapter 15) is never trusted on first contact with real
traffic. `Canary` routes a stable, deterministic slice of traffic to the candidate
so the same case always lands in the same arm. `ShadowRunner` runs the candidate
alongside the current bundle, *serves the current output*, and records what the
candidate would have done — production-realistic evaluation at zero user risk. The
shadow report highlights the only diffs that matter for a safety-critical agent:
where the candidate is *less* conservative than the bundle in production.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from .types import APPROVE, ESCALATE, FLAG, Review

# How conservative each verdict is. A candidate that moves a case *down* this scale
# (e.g. ESCALATE -> APPROVE) is a potential safety regression and must be caught.
_CONSERVATISM = {APPROVE: 0, FLAG: 1, ESCALATE: 2}


def _stable_fraction(key: str, salt: str) -> float:
    """Map a key to a stable value in [0, 1) via a hash — no per-call randomness."""
    digest = hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


@dataclass(frozen=True)
class Canary:
    """Routes a deterministic fraction of traffic to the candidate bundle."""
    fraction: float
    salt: str = "medguard-canary"

    def routes_to_candidate(self, case_id: str) -> bool:
        if self.fraction <= 0:
            return False
        if self.fraction >= 1:
            return True
        return _stable_fraction(case_id, self.salt) < self.fraction


@dataclass(frozen=True)
class ShadowComparison:
    case_id: str
    served: str        # verdict actually returned to the user (current bundle)
    shadow: str        # verdict the candidate would have produced
    agreed: bool
    candidate_less_safe: bool  # candidate less conservative than current -> risk


ReviewFn = Callable[[dict], Review]


class ShadowRunner:
    """Runs candidate in shadow, serving the current bundle's result."""

    def __init__(self, current: ReviewFn, candidate: ReviewFn):
        self._current = current
        self._candidate = candidate
        self.comparisons: list[ShadowComparison] = []

    def run(self, case: dict) -> Review:
        served = self._current(case)
        shadow = self._candidate(case)
        self.comparisons.append(ShadowComparison(
            case_id=str(case.get("id", "unknown")),
            served=served.verdict,
            shadow=shadow.verdict,
            agreed=served.verdict == shadow.verdict,
            candidate_less_safe=_CONSERVATISM[shadow.verdict] < _CONSERVATISM[served.verdict],
        ))
        return served  # the user always gets the current, trusted output

    def report(self) -> dict:
        n = len(self.comparisons)
        agree = sum(c.agreed for c in self.comparisons)
        regressions = [c for c in self.comparisons if c.candidate_less_safe]
        return {
            "n": n,
            "agreement_rate": round(agree / n, 4) if n else 1.0,
            "safety_regressions": len(regressions),
            "regression_cases": [c.case_id for c in regressions],
        }

    def safe_to_promote(self) -> bool:
        """A candidate is promotable only if it never regressed safety in shadow."""
        return all(not c.candidate_less_safe for c in self.comparisons)
