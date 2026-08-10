"""MedGuard tools — deterministic checks that stand in for grounded tool calls.

In a deployment with a real model and live data sources, these would be tool
calls the agent orchestrates (Chapter 9) against grounded sources (Chapter 8). In
the book's offline mode they're a small, deterministic knowledge base so the whole
agent runs and is testable without a network. Each returns structured `Finding`s
with citations, and signals failure explicitly rather than returning a misleading
empty result.

v3.2 hardens the boundary (Chapter 9): tool arguments are validated before a call
runs, calls execute under a timeout with safe (idempotent-only) retries, and every
failure surfaces as an explicit `ToolError` — never as an empty-but-successful
result.
"""

from __future__ import annotations

import concurrent.futures
from typing import Callable, TypeVar

from .types import Finding

_T = TypeVar("_T")

# Reliability defaults for a read-only lookup. A real deployment would tune these
# per tool and per environment; they live here so the policy is explicit.
DEFAULT_TIMEOUT_S = 2.0
DEFAULT_RETRIES = 2

# --- Minimal built-in "drug knowledge" (illustrative, NOT clinical reference) ---

# Pairwise interactions, keyed by the unordered pair of drug names.
_INTERACTIONS: dict[frozenset[str], tuple[str, str, str]] = {
    frozenset({"warfarin", "ciprofloxacin"}): (
        "moderate",
        "Ciprofloxacin potentiates warfarin, raising bleeding risk; needs INR monitoring or an alternative.",
        "BNF: warfarin — interactions",
    ),
    frozenset({"methotrexate", "trimethoprim"}): (
        "high",
        "Trimethoprim with methotrexate risks severe bone-marrow suppression; effectively contraindicated.",
        "BNF: methotrexate — interactions",
    ),
}


class ToolError(RuntimeError):
    """Raised when a tool cannot complete — never silently treated as 'all clear'."""


class TransientToolError(ToolError):
    """A retryable failure (timeout, transient network error). Safe to retry only
    for idempotent calls."""


def call_reliably(
    fn: Callable[..., _T],
    *args,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    retries: int = DEFAULT_RETRIES,
    idempotent: bool = True,
) -> _T:
    """Run a tool under a timeout with safe retries.

    Only *idempotent* calls are retried, so a retry can never cause a duplicate
    side effect (Chapter 9). A timeout or transient error is retried up to
    `retries` times; any other exception is wrapped as a `ToolError` so a failure
    can never be mistaken for a clean, empty result.
    """
    attempts = retries + 1 if idempotent else 1
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(fn, *args).result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            last_exc = TransientToolError(
                f"{getattr(fn, '__name__', 'tool')} timed out after {timeout_s}s")
        except TransientToolError as exc:
            last_exc = exc
        except ToolError:
            raise  # a validation/permanent tool error is not retryable
        except Exception as exc:  # unknown failure -> explicit, never silent
            raise ToolError(
                f"{getattr(fn, '__name__', 'tool')} failed: {exc}") from exc
    assert last_exc is not None
    raise last_exc


def _validate_interaction_args(current_medications, proposed) -> None:
    """Reject malformed arguments before the tool runs (Chapter 9 schema check)."""
    if not isinstance(proposed, dict):
        raise ToolError("proposed must be an object")
    if not isinstance(current_medications, list):
        raise ToolError("current_medications must be a list")
    if not (proposed.get("drug") or "").strip():
        raise ToolError("proposed drug missing")


def check_interactions(current_medications: list[dict], proposed: dict) -> list[Finding]:
    """Find interactions between the proposed drug and each current medication."""
    _validate_interaction_args(current_medications, proposed)
    proposed_drug = proposed["drug"].strip().lower()
    findings: list[Finding] = []
    for med in current_medications:
        current = (med.get("drug") or "").strip().lower()
        hit = _INTERACTIONS.get(frozenset({current, proposed_drug}))
        if hit:
            severity, explanation, citation = hit
            findings.append(Finding("interaction", severity, explanation, citation, source="tool"))
    return findings


def check_contraindications(patient: dict, proposed: dict) -> list[Finding]:
    """Placeholder contraindication check (no rules in the illustrative KB yet)."""
    return []
