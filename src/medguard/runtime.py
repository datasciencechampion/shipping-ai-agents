"""Scaling primitives for MedGuard (v5.2): concurrency, rate limits, backpressure.

Scaling a safety-critical agent is mostly ordinary distributed-systems work with
one twist (Chapter 17): degradation under load must respect the same safety
invariants as normal operation. A `TokenBucket` respects downstream rate limits; a
`BoundedQueue` applies backpressure instead of accepting unbounded work; and
`SafeDegrader` ties them together so an overloaded system *escalates to a human* —
it never drops a case or rushes an unsafe answer. Concurrent reviews are safe
because each `review_case` call owns its state (Chapter 10), which `run_concurrent`
relies on.
"""

from __future__ import annotations

import concurrent.futures
import time
from collections import deque
from typing import Callable

from .types import ESCALATE, Review

ReviewFn = Callable[[dict], Review]


class TokenBucket:
    """A classic token-bucket limiter for respecting a downstream rate limit."""

    def __init__(self, capacity: float, refill_per_s: float, *, clock=time.monotonic):
        self.capacity = capacity
        self.refill_per_s = refill_per_s
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.refill_per_s)
        self._last = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False


class BoundedQueue:
    """A fixed-capacity queue. `offer` fails (backpressure) instead of growing."""

    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self._items: deque = deque()

    def __len__(self) -> int:
        return len(self._items)

    def offer(self, item) -> bool:
        if len(self._items) >= self.maxsize:
            return False  # backpressure: caller must handle, not block forever
        self._items.append(item)
        return True

    def poll(self):
        return self._items.popleft() if self._items else None


class SafeDegrader:
    """Admits work under a rate limit + bounded queue; degrades to escalation.

    When the system cannot admit a case, the result is an ESCALATE review (route to
    a human), never a dropped or rushed one — the safety invariant holds under load.
    """

    def __init__(self, limiter: TokenBucket, queue: BoundedQueue):
        self._limiter = limiter
        self._queue = queue
        self.shed = 0

    def submit(self, case: dict, review_fn: ReviewFn) -> Review:
        if not self._limiter.try_acquire():
            return self._degrade(case, "rate_limited")
        if not self._queue.offer(case):
            return self._degrade(case, "queue_full")
        try:
            return review_fn(case)
        finally:
            self._queue.poll()

    def _degrade(self, case: dict, reason: str) -> Review:
        self.shed += 1
        return Review(ESCALATE, [], 0.5, trace_id=None)


def run_concurrent(cases: list[dict], review_fn: ReviewFn, *, max_workers: int = 8) -> list[Review]:
    """Review many cases concurrently, preserving input order.

    Safe because each review owns its state; there is no shared mutable memory
    across cases (the isolation guarantee of Chapter 10).
    """
    results: list[Review | None] = [None] * len(cases)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(review_fn, case): i for i, case in enumerate(cases)}
        for fut in concurrent.futures.as_completed(futures):
            results[futures[fut]] = fut.result()
    return results  # type: ignore[return-value]
