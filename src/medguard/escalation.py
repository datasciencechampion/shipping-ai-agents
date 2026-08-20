"""Human-in-the-loop escalation for MedGuard (v4).

Escalation is a first-class outcome, not an error path (Chapter 11). Three things
send a case to a human: a high-severity finding, a tool failure, or low decision
confidence. This module owns the confidence-threshold routing, the queue a
pharmacist actually works from, and the feedback loop that turns each resolved
escalation into a new labeled golden case (Chapter 16).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .types import ESCALATE, Review


def needs_human(review: Review, *, min_confidence: float) -> tuple[bool, str]:
    """Decide whether a review should go to a human, with a reason.

    Returns (True, reason) when the case must be escalated. A review that already
    escalated stays escalated; otherwise a below-threshold confidence routes it to
    a human even if the verdict itself was APPROVE/FLAG.
    """
    if review.verdict == ESCALATE:
        return True, "verdict_escalate"
    if review.confidence < min_confidence:
        return True, "low_confidence"
    return False, ""


@dataclass
class EscalationItem:
    case_id: str
    case: dict
    review: Review
    reason: str
    created_at: float = field(default_factory=time.time)
    resolution: str | None = None  # pharmacist's ground-truth verdict, once known


class EscalationQueue:
    """An in-memory queue of cases awaiting human review."""

    def __init__(self) -> None:
        self._items: list[EscalationItem] = []

    def __len__(self) -> int:
        return len([i for i in self._items if i.resolution is None])

    def enqueue(self, case: dict, review: Review, reason: str) -> EscalationItem:
        item = EscalationItem(
            case_id=str(case.get("id", "unknown")),
            case=case, review=review, reason=reason)
        self._items.append(item)
        return item

    def pending(self) -> list[EscalationItem]:
        return [i for i in self._items if i.resolution is None]

    def resolve(self, item: EscalationItem, pharmacist_verdict: str) -> dict:
        """Record a human resolution and return a golden case built from it."""
        item.resolution = pharmacist_verdict
        return feedback_to_golden_case(item)


def feedback_to_golden_case(item: EscalationItem) -> dict:
    """Turn a resolved escalation into a labeled case for the golden set.

    This is the loop that makes the eval set grow from real traffic: every case a
    human had to touch becomes a regression test so the agent never mishandles its
    like again.
    """
    return {
        "id": f"esc-{item.case_id}",
        "patient": item.case.get("patient", {}),
        "current_medications": item.case.get("current_medications", []),
        "proposed": item.case.get("proposed", {}),
        "expected_verdict": item.resolution,
        "expected_severity": item.review.max_severity(),
        "origin": "escalation_feedback",
    }
