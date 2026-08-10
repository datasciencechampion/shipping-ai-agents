"""Tests for v5 progressive rollout: canary routing and shadow mode."""

from medguard.rollout import Canary, ShadowRunner
from medguard.types import APPROVE, ESCALATE, FLAG, Review


def _fixed(verdict):
    return lambda case: Review(verdict, [], 0.9, "t")


def test_canary_routing_is_stable_and_proportional():
    canary = Canary(fraction=0.5)
    ids = [f"case-{i}" for i in range(1000)]
    routed = [canary.routes_to_candidate(i) for i in ids]
    # Same id always routes the same way (determinism).
    assert all(canary.routes_to_candidate(i) == r for i, r in zip(ids, routed))
    # Roughly the requested fraction (loose bounds, deterministic hash).
    frac = sum(routed) / len(routed)
    assert 0.4 < frac < 0.6


def test_canary_zero_and_full_fractions():
    assert Canary(0.0).routes_to_candidate("x") is False
    assert Canary(1.0).routes_to_candidate("x") is True


def test_shadow_serves_current_and_records_candidate():
    runner = ShadowRunner(current=_fixed(FLAG), candidate=_fixed(ESCALATE))
    served = runner.run({"id": "c1"})
    assert served.verdict == FLAG  # user gets the current bundle's output
    rep = runner.report()
    assert rep["n"] == 1
    assert rep["safety_regressions"] == 0  # candidate was MORE conservative


def test_shadow_flags_safety_regression():
    # Candidate approves where current escalates -> a safety regression.
    runner = ShadowRunner(current=_fixed(ESCALATE), candidate=_fixed(APPROVE))
    runner.run({"id": "danger-1"})
    rep = runner.report()
    assert rep["safety_regressions"] == 1
    assert rep["regression_cases"] == ["danger-1"]
    assert runner.safe_to_promote() is False


def test_shadow_promotable_when_no_regressions():
    runner = ShadowRunner(current=_fixed(APPROVE), candidate=_fixed(FLAG))
    for i in range(5):
        runner.run({"id": f"c{i}"})
    assert runner.safe_to_promote() is True
    assert runner.report()["agreement_rate"] == 0.0  # differed, but more conservative
