"""Tests for v3.1 grounding and citation verification."""

from medguard.grounding import is_grounded, source_text, verify_findings
from medguard.pipeline import review_case
from medguard.types import ESCALATE, Finding

_WARFARIN = {
    "patient": {"age": 60, "egfr_ml_min": 88, "conditions": ["atrial fibrillation"]},
    "current_medications": [{"drug": "warfarin", "dose": "5 mg", "frequency": "once daily"}],
    "proposed": {"drug": "ciprofloxacin", "dose": "500 mg", "frequency": "twice daily"},
}


def test_known_citation_is_grounded():
    assert is_grounded("BNF: warfarin — interactions")
    assert source_text("BNF: warfarin — interactions")


def test_unknown_or_missing_citation_is_not_grounded():
    assert not is_grounded("BNF: fictional drug — invented interaction")
    assert not is_grounded(None)
    assert not is_grounded("")


def test_verify_findings_splits_grounded_from_hallucinated():
    good = Finding("interaction", "moderate", "real", "BNF: warfarin — interactions", source="tool")
    bad = Finding("interaction", "high", "made up", "BNF: nonexistent", source="model")
    missing = Finding("interaction", "low", "no cite", None, source="model")
    verified, unverified = verify_findings([good, bad, missing])
    assert verified == [good]
    assert set(unverified) == {bad, missing}


def test_real_tool_findings_pass_verification_in_pipeline():
    # The warfarin interaction carries a grounded citation, so it is NOT escalated
    # for lack of grounding — it flags on its own (moderate) merits.
    r = review_case(_WARFARIN)
    assert r.verdict != ESCALATE
    assert all(f.citation for f in r.findings)


def test_ungrounded_finding_forces_escalation():
    # A moderate finding that would normally FLAG is escalated when its citation
    # cannot be grounded: we refuse to act on a possibly hallucinated source.
    import medguard.pipeline as pipe

    original = pipe.check_interactions

    def fake_check(current, proposed):
        return [Finding("interaction", "moderate", "looks real",
                        "BNF: invented source", source="model")]

    pipe.check_interactions = fake_check
    try:
        r = review_case(_WARFARIN)
        assert r.verdict == ESCALATE
    finally:
        pipe.check_interactions = original
