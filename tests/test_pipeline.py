"""Tests for the v3+ structured review pipeline (bounded state machine)."""

from medguard.pipeline import review_case
from medguard.types import APPROVE, ESCALATE, FLAG

_SAFE = {
    "patient": {"age": 55, "egfr_ml_min": 90, "conditions": ["hypertension"]},
    "current_medications": [],
    "proposed": {"drug": "amlodipine", "dose": "5 mg", "frequency": "once daily"},
}
_WARFARIN = {
    "patient": {"age": 60, "egfr_ml_min": 88, "conditions": ["atrial fibrillation"]},
    "current_medications": [{"drug": "warfarin", "dose": "5 mg", "frequency": "once daily"}],
    "proposed": {"drug": "ciprofloxacin", "dose": "500 mg", "frequency": "twice daily"},
}
_METHOTREXATE = {
    "patient": {"age": 58, "egfr_ml_min": 75, "conditions": ["rheumatoid arthritis"]},
    "current_medications": [{"drug": "methotrexate", "dose": "15 mg", "frequency": "once weekly"}],
    "proposed": {"drug": "trimethoprim", "dose": "200 mg", "frequency": "twice daily"},
}
_GABA = {
    "patient": {"age": 82, "egfr_ml_min": 22, "conditions": ["chronic kidney disease stage 4"]},
    "current_medications": [{"drug": "metformin", "dose": "500 mg", "frequency": "twice daily"}],
    "proposed": {"drug": "gabapentin", "dose": "600 mg", "frequency": "three times daily"},
}


def test_safe_case_approved_with_no_findings():
    r = review_case(_SAFE)
    assert r.verdict == APPROVE
    assert r.findings == []
    assert r.trace_id


def test_moderate_interaction_flagged():
    r = review_case(_WARFARIN)
    assert r.verdict == FLAG
    assert any(f.type == "interaction" for f in r.findings)


def test_high_interaction_escalates():
    r = review_case(_METHOTREXATE)
    assert r.verdict == ESCALATE
    assert r.max_severity() == "high"


def test_v3_misses_renal_dose_but_v41_guardrail_catches_it():
    # Without guardrails (v3), the reasoner has no renal dose model -> approves.
    assert review_case(_GABA, guardrails=False).verdict == APPROVE
    # With guardrails (v4.1), the independent dose-ceiling veto forces escalation.
    r41 = review_case(_GABA, guardrails=True)
    assert r41.verdict == ESCALATE
    assert any(f.source == "guardrail" for f in r41.findings)


def test_step_budget_forces_safe_termination():
    r = review_case(_SAFE, step_budget=1)
    assert r.verdict == ESCALATE  # ran out of budget -> escalate to a human
