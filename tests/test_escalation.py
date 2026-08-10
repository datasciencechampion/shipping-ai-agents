"""Tests for v4 human-in-the-loop escalation: routing, queue, feedback loop."""

from medguard.escalation import (
    EscalationQueue,
    feedback_to_golden_case,
    needs_human,
)
from medguard.pipeline import review_case
from medguard.types import APPROVE, ESCALATE, FLAG, Finding, Review

_SAFE = {
    "id": "safe-1",
    "patient": {"age": 55, "egfr_ml_min": 90, "conditions": ["hypertension"]},
    "current_medications": [],
    "proposed": {"drug": "amlodipine", "dose": "5 mg", "frequency": "once daily"},
}
_METHOTREXATE = {
    "id": "mtx-1",
    "patient": {"age": 58, "egfr_ml_min": 75, "conditions": ["rheumatoid arthritis"]},
    "current_medications": [{"drug": "methotrexate", "dose": "15 mg", "frequency": "once weekly"}],
    "proposed": {"drug": "trimethoprim", "dose": "200 mg", "frequency": "twice daily"},
}


def test_escalate_verdict_always_needs_human():
    r = Review(ESCALATE, [], 0.95)
    go, reason = needs_human(r, min_confidence=0.6)
    assert go and reason == "verdict_escalate"


def test_low_confidence_routes_to_human():
    r = Review(APPROVE, [], 0.4)
    go, reason = needs_human(r, min_confidence=0.6)
    assert go and reason == "low_confidence"


def test_confident_approval_does_not_escalate():
    r = Review(APPROVE, [], 0.9)
    go, _ = needs_human(r, min_confidence=0.6)
    assert not go


def test_queue_tracks_pending_and_resolution():
    q = EscalationQueue()
    review = review_case(_METHOTREXATE)
    item = q.enqueue(_METHOTREXATE, review, reason="verdict_escalate")
    assert len(q) == 1
    assert q.pending() == [item]
    golden = q.resolve(item, pharmacist_verdict=ESCALATE)
    assert len(q) == 0  # resolved items leave the pending count
    assert golden["expected_verdict"] == ESCALATE


def test_feedback_becomes_labeled_golden_case():
    review = Review(FLAG, [Finding("interaction", "moderate", "x", "BNF: warfarin — interactions")], 0.7)
    q = EscalationQueue()
    item = q.enqueue(_SAFE, review, reason="low_confidence")
    golden = feedback_to_golden_case(_with_resolution(item, FLAG))
    assert golden["id"] == "esc-safe-1"
    assert golden["expected_verdict"] == FLAG
    assert golden["expected_severity"] == "moderate"
    assert golden["origin"] == "escalation_feedback"


def test_pipeline_min_confidence_escalates_borderline_approval():
    # With a high confidence bar, even a clean APPROVE is routed to a human.
    r = review_case(_SAFE, min_confidence=0.95)
    assert r.verdict == ESCALATE
    # With the default bar (0.0), the same case approves.
    assert review_case(_SAFE).verdict == APPROVE


def _with_resolution(item, verdict):
    item.resolution = verdict
    return item
