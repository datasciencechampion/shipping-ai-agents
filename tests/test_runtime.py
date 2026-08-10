"""Tests for v5.2 scaling: rate limits, backpressure, safe degradation, concurrency."""

from medguard.pipeline import review_case
from medguard.runtime import (
    BoundedQueue,
    SafeDegrader,
    TokenBucket,
    run_concurrent,
)
from medguard.types import APPROVE, ESCALATE, Review

_SAFE = {
    "id": "safe-1",
    "patient": {"age": 55, "egfr_ml_min": 90, "conditions": ["hypertension"]},
    "current_medications": [],
    "proposed": {"drug": "amlodipine", "dose": "5 mg", "frequency": "once daily"},
}
_GABA = {
    "id": "gaba-1",
    "patient": {"age": 82, "egfr_ml_min": 22, "conditions": ["ckd stage 4"]},
    "current_medications": [{"drug": "metformin", "dose": "500 mg", "frequency": "twice daily"}],
    "proposed": {"drug": "gabapentin", "dose": "600 mg", "frequency": "three times daily"},
}


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def test_token_bucket_limits_then_refills():
    clock = _Clock()
    tb = TokenBucket(capacity=2, refill_per_s=1, clock=clock)
    assert tb.try_acquire() and tb.try_acquire()  # 2 tokens available
    assert tb.try_acquire() is False              # exhausted
    clock.advance(1.0)                            # +1 token
    assert tb.try_acquire() is True


def test_bounded_queue_applies_backpressure():
    q = BoundedQueue(maxsize=2)
    assert q.offer("a") and q.offer("b")
    assert q.offer("c") is False  # full -> backpressure
    assert q.poll() == "a"
    assert q.offer("c") is True   # space freed


def test_safe_degrader_escalates_when_rate_limited():
    clock = _Clock()
    limiter = TokenBucket(capacity=1, refill_per_s=0, clock=clock)  # never refills
    deg = SafeDegrader(limiter, BoundedQueue(maxsize=10))
    first = deg.submit(_SAFE, review_case)   # admitted
    second = deg.submit(_SAFE, review_case)  # rate limited -> degrade
    assert first.verdict == APPROVE
    assert second.verdict == ESCALATE        # degraded to human, not dropped
    assert deg.shed == 1


def test_safe_degrader_escalates_when_queue_full():
    limiter = TokenBucket(capacity=100, refill_per_s=100)
    deg = SafeDegrader(limiter, BoundedQueue(maxsize=0))  # no capacity at all
    r = deg.submit(_SAFE, review_case)
    assert r.verdict == ESCALATE
    assert deg.shed == 1


def test_concurrent_reviews_match_sequential_and_preserve_order():
    cases = [_SAFE, _GABA, _SAFE, _GABA]
    sequential = [review_case(c).verdict for c in cases]
    concurrent_results = [r.verdict for r in run_concurrent(cases, review_case, max_workers=4)]
    # Isolation: concurrency changes nothing about the per-case outcome or order.
    assert concurrent_results == sequential
    assert concurrent_results == [APPROVE, ESCALATE, APPROVE, ESCALATE]
