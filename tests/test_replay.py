"""Snapshot / trace-replay tests.

Two regression nets that need no live model:

1. The fake agent's output must still match the committed snapshot. If someone
   changes the agent and the snapshot drifts, this fails loudly.
2. Replaying the recorded outputs through the scorer must reproduce the exact
   safety verdict from Chapter 3 (80% overall, 3 unsafe approvals, 2 high). This
   guards the whole evaluation pipeline offline and deterministically.
"""

from pathlib import Path

from medguard.agent import review
from medguard.config import Config
from medguard.eval.scoring import score
from medguard.testing import load_cases, load_snapshot

_HERE = Path(__file__).resolve().parent
_SNAPSHOT = _HERE / "fixtures" / "v0_golden_outputs.json"
_GOLDEN = _HERE.parent / "evals" / "golden_set.json"


def test_fake_outputs_match_snapshot():
    snapshot = load_snapshot(_SNAPSHOT)
    cfg = Config(fake=True)
    for case in load_cases(_GOLDEN):
        assert review(case, cfg) == snapshot[case["case_id"]]


def test_replayed_scoring_reproduces_the_dangerous_tail():
    snapshot = load_snapshot(_SNAPSHOT)
    cases = load_cases(_GOLDEN)
    report = score(cases, lambda c: snapshot[c["case_id"]])

    assert report.total == 15
    assert report.accuracy == 12 / 15  # 80%
    assert len(report.unsafe_approvals) == 3
    assert len(report.high_severity_unsafe) == 2
    assert report.passed is False
