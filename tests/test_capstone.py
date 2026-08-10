"""Tests for the Chapter 19 capstone: the finished end-to-end review path."""

from medguard.audit import AuditLog, scan_for_phi
from medguard.capstone import review_end_to_end
from medguard.escalation import EscalationQueue
from medguard.ops import KillSwitch
from medguard.types import APPROVE, ESCALATE

_SAFE = {
    "id": "safe-1",
    "patient": {"name": "Ada L.", "mrn": "MRN-1", "age": 55, "egfr_ml_min": 90,
                "conditions": ["hypertension"]},
    "current_medications": [],
    "proposed": {"drug": "amlodipine", "dose": "5 mg", "frequency": "once daily"},
}
# The Chapter 1 renal overdose: standard dose, dangerous for egfr 22.
_RENAL_OVERDOSE = {
    "id": "ch01-renal-overdose",
    "patient": {"name": "John Q.", "mrn": "MRN-9", "age": 82, "egfr_ml_min": 22,
                "conditions": ["chronic kidney disease stage 4"]},
    "current_medications": [{"drug": "metformin", "dose": "500 mg", "frequency": "twice daily"}],
    "proposed": {"drug": "gabapentin", "dose": "600 mg", "frequency": "three times daily"},
}
_IDENTIFIERS = {"Ada L.", "MRN-1", "John Q.", "MRN-9"}


def test_safe_case_approves_and_does_not_escalate():
    result = review_end_to_end(_SAFE)
    assert result.review.verdict == APPROVE
    assert result.escalated is False
    assert result.audit["verdict"] == APPROVE


def test_chapter1_overdose_is_now_impossible_to_approve():
    # The whole point of the book, exercised end to end: v0 approved this; the
    # finished system escalates it via the independent dose-ceiling veto.
    queue = EscalationQueue()
    result = review_end_to_end(_RENAL_OVERDOSE, queue=queue)
    assert result.review.verdict == ESCALATE
    assert result.escalated is True
    assert len(queue) == 1  # it landed in the pharmacist's queue


def test_kill_switch_degrades_to_human():
    ks = KillSwitch()
    ks.engage("provider incident")
    assert review_end_to_end(_SAFE, kill_switch=ks).review.verdict == ESCALATE


def test_audit_trail_is_phi_safe_and_records_boundary():
    log = AuditLog()
    review_end_to_end(_SAFE, audit_log=log)
    review_end_to_end(_RENAL_OVERDOSE, audit_log=log)
    log.assert_clean(_IDENTIFIERS)  # no identifier leaked into the trail
    # Only clinical fields crossed the provider boundary — never name/mrn.
    for rec in [review_end_to_end(_SAFE).audit]:
        assert "name" not in rec["provider_fields"]
        assert "mrn" not in rec["provider_fields"]
        assert "age" in rec["provider_fields"]


def test_result_audit_has_trace_and_findings():
    result = review_end_to_end(_RENAL_OVERDOSE)
    assert result.audit["trace_id"] == result.review.trace_id
    assert scan_for_phi(result.audit, _IDENTIFIERS) == []  # identity redacted
