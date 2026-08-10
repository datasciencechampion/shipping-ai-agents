"""Continuous evaluation and drift detection for MedGuard (v5.1).

Evaluation doesn't end at the launch gate (Chapter 16). `should_sample` selects a
stable slice of live traffic for online scoring; `OnlineMetrics` tracks the signal
that matters most — the unsafe-approval rate — for Chapter 6's alerts. `DriftMonitor`
watches a trend rather than a single day, so a slow slide is caught before it
becomes an incident. And `merge_feedback` closes the flywheel: escalations and
corrections (Chapter 11) become new golden cases, so the eval set grows toward
exactly the cases reality proves hardest.
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field

from .types import APPROVE

# Verdicts that are unsafe when the ground truth was more serious than APPROVE.
_UNSAFE_WHEN_APPROVED = APPROVE


def should_sample(case_id: str, rate: float, salt: str = "medguard-online") -> bool:
    """Deterministically sample a `rate` fraction of traffic for online scoring."""
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    digest = hashlib.sha256(f"{salt}:{case_id}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < rate


@dataclass
class OnlineMetrics:
    """Running online-eval counters. Ground truth arrives from human review."""
    total: int = 0
    correct: int = 0
    unsafe_approvals: int = 0

    def record(self, expected: str, predicted: str) -> None:
        self.total += 1
        if predicted == expected:
            self.correct += 1
        # Unsafe approval: agent approved something the truth said was not safe.
        if predicted == _UNSAFE_WHEN_APPROVED and expected != _UNSAFE_WHEN_APPROVED:
            self.unsafe_approvals += 1

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 1.0

    @property
    def unsafe_rate(self) -> float:
        return self.unsafe_approvals / self.total if self.total else 0.0


@dataclass
class DriftMonitor:
    """Flags a downward trend in a quality score against a baseline.

    Watches a rolling window; only reports drift once the window is full, so a
    couple of unlucky samples don't trip a false alarm.
    """
    baseline: float
    window: int = 20
    min_drop: float = 0.05
    _scores: deque = field(default_factory=deque)

    def push(self, score: float) -> None:
        self._scores.append(score)
        while len(self._scores) > self.window:
            self._scores.popleft()

    @property
    def rolling_mean(self) -> float:
        return sum(self._scores) / len(self._scores) if self._scores else self.baseline

    def drifted(self) -> bool:
        if len(self._scores) < self.window:
            return False
        return self.rolling_mean < self.baseline - self.min_drop


def merge_feedback(golden_cases: list[dict], feedback_cases: list[dict]) -> list[dict]:
    """Fold resolved-escalation cases into the golden set, de-duplicated by id.

    Feedback wins on conflict: the human's ground truth is the authority.
    """
    by_id: dict[str, dict] = {str(c.get("id")): c for c in golden_cases}
    for c in feedback_cases:
        by_id[str(c.get("id"))] = c
    return list(by_id.values())
