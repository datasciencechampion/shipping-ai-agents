"""Tests for v4.2 cost/latency budgets and the model cascade."""

from medguard.budget import (
    Budget,
    BudgetTracker,
    cost_usd,
    next_model,
    run_cascade,
)
from medguard.pipeline import review_case
from medguard.types import APPROVE, ESCALATE

_SAFE = {
    "patient": {"age": 55, "egfr_ml_min": 90, "conditions": ["hypertension"]},
    "current_medications": [],
    "proposed": {"drug": "amlodipine", "dose": "5 mg", "frequency": "once daily"},
}


class _StepClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_cost_is_priced_per_model():
    cheap = cost_usd("gpt-4o-mini", 800, 200)
    dear = cost_usd("gpt-4o", 800, 200)
    assert dear > cheap > 0


def test_tracker_flags_cost_overrun():
    clock = _StepClock()
    t = BudgetTracker(Budget(max_usd=0.0001, max_latency_ms=10_000), clock=clock)
    t.record("gpt-4o", 800, 200)  # far above the tiny cost ceiling
    assert t.status() == "over_cost"
    assert t.over_budget()


def test_tracker_flags_latency_overrun():
    clock = _StepClock()
    t = BudgetTracker(Budget(max_usd=1.0, max_latency_ms=100.0), clock=clock)
    clock.advance(0.2)  # 200 ms elapsed, ceiling is 100 ms
    assert t.status() == "over_latency"


def test_next_model_walks_up_the_cascade():
    assert next_model("gpt-4o-mini") == "gpt-4o"
    assert next_model("gpt-4.1") is None  # already the strongest
    assert next_model("unknown") == "gpt-4o-mini"


def test_cascade_stops_at_first_confident_model():
    confidences = {"gpt-4o-mini": 0.95, "gpt-4o": 0.99}
    result, conf, model, escalated = run_cascade(
        lambda m: (m, confidences[m]), min_confidence=0.8)
    assert model == "gpt-4o-mini"  # cheap model was confident enough
    assert not escalated


def test_cascade_escalates_when_cheap_model_is_unsure():
    confidences = {"gpt-4o-mini": 0.4, "gpt-4o": 0.9, "gpt-4.1": 0.99}
    result, conf, model, escalated = run_cascade(
        lambda m: (m, confidences[m]), min_confidence=0.85)
    assert model == "gpt-4o"  # escalated one rung, stopped when confident
    assert escalated


def test_pipeline_escalates_on_budget_overrun():
    # A tiny cost budget forces even a clean approval to a human (overflow path).
    tiny = Budget(max_usd=0.0000001, max_latency_ms=10_000)
    assert review_case(_SAFE, budget=tiny).verdict == ESCALATE
    # A generous budget leaves the verdict untouched.
    ample = Budget(max_usd=1.0, max_latency_ms=10_000)
    assert review_case(_SAFE, budget=ample).verdict == APPROVE


def test_no_budget_is_unchanged_behavior():
    assert review_case(_SAFE).verdict == APPROVE
