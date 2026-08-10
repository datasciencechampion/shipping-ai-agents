"""Cost and latency budgets for MedGuard (v4.2).

Cost and latency are product requirements, enforced like SLOs (Chapter 13). This
module turns the token/latency data already on the trace (Chapter 5) into a
per-request budget: a `BudgetTracker` accumulates spend and elapsed time, and
reports when a request has blown its ceiling. A model *cascade* tries a cheap
model first and only escalates to a stronger one when confidence is low, so the
easy middle of the distribution never pays for the most expensive model.

When a request exceeds budget on a hard case, the safe fallback doubles as the
overflow path: escalate to a human (Chapter 11).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

_T = TypeVar("_T")

# Illustrative prices, USD per 1K tokens (input, output). NOT current vendor rates.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o": (0.00500, 0.01500),
    "gpt-4.1": (0.01000, 0.03000),
}

# The cascade, cheapest first. `next_model` walks toward stronger models.
CASCADE: tuple[str, ...] = ("gpt-4o-mini", "gpt-4o", "gpt-4.1")


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cost of one model call. Unknown models are priced at 0 (and should alert)."""
    in_rate, out_rate = MODEL_PRICES.get(model, (0.0, 0.0))
    return round((tokens_in * in_rate + tokens_out * out_rate) / 1000, 8)


@dataclass(frozen=True)
class Budget:
    max_usd: float
    max_latency_ms: float


class BudgetTracker:
    """Accumulates per-request cost and latency and reports budget status."""

    def __init__(self, budget: Budget, *, clock=time.perf_counter) -> None:
        self.budget = budget
        self._clock = clock
        self._start = clock()
        self.spent_usd = 0.0
        self.calls = 0

    def record(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Record one model call; returns its cost."""
        c = cost_usd(model, tokens_in, tokens_out)
        self.spent_usd = round(self.spent_usd + c, 8)
        self.calls += 1
        return c

    @property
    def elapsed_ms(self) -> float:
        return round((self._clock() - self._start) * 1000, 3)

    def status(self) -> str:
        """One of: 'ok', 'over_cost', 'over_latency'."""
        if self.spent_usd > self.budget.max_usd:
            return "over_cost"
        if self.elapsed_ms > self.budget.max_latency_ms:
            return "over_latency"
        return "ok"

    def over_budget(self) -> bool:
        return self.status() != "ok"


def next_model(current: str, cascade: tuple[str, ...] = CASCADE) -> str | None:
    """The next stronger model in the cascade, or None if `current` is the top."""
    try:
        idx = cascade.index(current)
    except ValueError:
        return cascade[0] if cascade else None
    return cascade[idx + 1] if idx + 1 < len(cascade) else None


def run_cascade(
    attempt: Callable[[str], tuple[_T, float]],
    *,
    cascade: tuple[str, ...] = CASCADE,
    min_confidence: float,
) -> tuple[_T, float, str, bool]:
    """Try models cheapest-first, stopping at the first confident-enough result.

    `attempt(model)` returns (result, confidence). Returns
    (result, confidence, model_used, escalated) where `escalated` is True if any
    model beyond the cheapest was used. If no model clears the bar, the strongest
    model's result is returned — the caller can still route it to a human.
    """
    result: _T | None = None
    confidence = 0.0
    model_used = cascade[0]
    for i, model in enumerate(cascade):
        result, confidence = attempt(model)
        model_used = model
        if confidence >= min_confidence:
            return result, confidence, model_used, i > 0
    return result, confidence, model_used, len(cascade) > 1  # type: ignore[return-value]
