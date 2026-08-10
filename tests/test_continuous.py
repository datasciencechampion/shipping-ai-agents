"""Tests for v5.1 continuous evaluation, drift detection, and the feedback flywheel."""

from medguard.continuous import (
    DriftMonitor,
    OnlineMetrics,
    merge_feedback,
    should_sample,
)
from medguard.types import APPROVE, ESCALATE, FLAG


def test_sampling_is_stable_and_proportional():
    ids = [f"case-{i}" for i in range(2000)]
    sampled = [should_sample(i, 0.1) for i in ids]
    assert all(should_sample(i, 0.1) == s for i, s in zip(ids, sampled))
    frac = sum(sampled) / len(sampled)
    assert 0.07 < frac < 0.13


def test_sampling_edge_rates():
    assert should_sample("x", 0.0) is False
    assert should_sample("x", 1.0) is True


def test_online_metrics_track_unsafe_approvals():
    m = OnlineMetrics()
    m.record(expected=ESCALATE, predicted=APPROVE)   # unsafe approval
    m.record(expected=FLAG, predicted=FLAG)          # correct
    m.record(expected=APPROVE, predicted=APPROVE)    # correct, safe
    assert m.total == 3
    assert m.unsafe_approvals == 1
    assert round(m.unsafe_rate, 3) == round(1 / 3, 3)
    assert round(m.accuracy, 3) == round(2 / 3, 3)


def test_drift_monitor_needs_full_window():
    d = DriftMonitor(baseline=0.95, window=5, min_drop=0.05)
    for _ in range(4):
        d.push(0.5)  # bad scores, but window not full yet
    assert d.drifted() is False
    d.push(0.5)
    assert d.drifted() is True


def test_drift_monitor_stable_quality_does_not_trip():
    d = DriftMonitor(baseline=0.90, window=5, min_drop=0.05)
    for _ in range(5):
        d.push(0.92)
    assert d.drifted() is False


def test_merge_feedback_dedupes_and_prefers_feedback():
    golden = [{"id": "a", "expected_verdict": APPROVE},
              {"id": "b", "expected_verdict": FLAG}]
    feedback = [{"id": "b", "expected_verdict": ESCALATE},  # correction wins
                {"id": "esc-1", "expected_verdict": ESCALATE}]
    merged = {c["id"]: c for c in merge_feedback(golden, feedback)}
    assert len(merged) == 3
    assert merged["b"]["expected_verdict"] == ESCALATE
    assert "esc-1" in merged
