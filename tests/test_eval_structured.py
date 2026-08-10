"""End-to-end: score the structured agents against the golden set.

Documents the safety progression the book describes:
  v3  (structured, no guardrails): 1 unsafe approval remains (the renal dose).
  v41 (structured + dose veto):     0 unsafe approvals -> gate PASSES.
"""

from pathlib import Path

from medguard.eval.scoring import score_structured
from medguard.pipeline import review_case
from medguard.testing import load_cases

_GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden_set.json"


def test_v41_passes_the_whole_golden_set():
    report = score_structured(load_cases(_GOLDEN), lambda c: review_case(c, guardrails=True))
    assert report.total == 15
    assert report.accuracy == 1.0
    assert report.unsafe_approvals == []
    assert report.passed


def test_v3_still_leaves_the_renal_dose_unsafe():
    report = score_structured(load_cases(_GOLDEN), lambda c: review_case(c, guardrails=False))
    assert len(report.unsafe_approvals) == 1
    assert len(report.high_severity_unsafe) == 1
    assert not report.passed
