"""The finished MedGuard, end to end (Chapter 19).

This module wires every subsystem the book built into one production-grade review
path. It adds no new cleverness; it composes the pieces in the right order so a
single call exhibits the whole discipline:

* v2.1 kill switch — degrade to a human without a deploy.
* v2   tracing — every step recorded under one trace_id + behavior bundle.
* v3   bounded state machine — a structured verdict, not prose.
* v3.1 grounding — findings escalate unless their citation verifies.
* v3.2 hardened tools — validated I/O, timeouts, safe retries.
* v4.1 independent guardrail — the dose-ceiling veto overrules the model.
* v4.2 cost/latency budget — an overrun routes to a human.
* v4   escalation — low-confidence or high-severity cases go to a pharmacist.
* v4.3 data boundary + audit — identity never leaves; every decision is provable.

Read it as the retrospective the chapter describes: the distance from v0's single
opaque call to this is the distance from a demo to a product.
"""

from __future__ import annotations

from dataclasses import dataclass

from .audit import AuditLog, build_audit_record, provider_payload
from .budget import Budget
from .escalation import EscalationQueue, needs_human
from .ops import BehaviorBundle, KillSwitch
from .pipeline import review_case
from .trace import Trace
from .types import Review

# The one behavior bundle that produced a decision — recorded in every trace so any
# past review is reproducible (Chapter 15).
DEFAULT_BUNDLE = BehaviorBundle(
    version="2026.07.0",
    model="gpt-4o-mini",
    prompt_version="v5",
    tools_version="v3.2",
    guardrails_version="v4.1",
)
# Generous enough that a normal review passes; a runaway request trips it.
DEFAULT_BUDGET = Budget(max_usd=0.05, max_latency_ms=10_000)
# The confidence bar below which a case is routed to a human (Chapter 11).
DEFAULT_MIN_CONFIDENCE = 0.6


@dataclass
class CapstoneResult:
    review: Review
    audit: dict
    escalated: bool
    escalation_reason: str


def review_end_to_end(
    case: dict,
    *,
    bundle: BehaviorBundle = DEFAULT_BUNDLE,
    budget: Budget | None = DEFAULT_BUDGET,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    kill_switch: KillSwitch | None = None,
    queue: EscalationQueue | None = None,
    audit_log: AuditLog | None = None,
    trace: Trace | None = None,
) -> CapstoneResult:
    """Run one review through the complete production path."""
    trace = trace or Trace()

    # Data boundary (Chapter 14): identity is stripped before anything could be sent
    # to a model provider. We compute it here to make the boundary explicit and to
    # record exactly which patient fields were allowed to cross it.
    provider_view = provider_payload(case)
    crossed_boundary = sorted(provider_view["patient"].keys())

    # The bounded, traced, grounded, guarded, budgeted review (Chapters 5-13).
    review = review_case(
        case,
        guardrails=True,
        kill_switch=kill_switch,
        verify_citations=True,
        min_confidence=min_confidence,
        bundle=bundle,
        budget=budget,
        trace=trace,
    )

    # Human-in-the-loop routing (Chapter 11): enqueue the cases a human must see.
    escalate, reason = needs_human(review, min_confidence=min_confidence)
    if escalate and queue is not None:
        queue.enqueue(case, review, reason)

    # Audit trail (Chapter 14): a redacted, provable record of what was decided,
    # including which patient fields were allowed to cross the provider boundary.
    if audit_log is not None:
        record = audit_log.record(case, review)
    else:
        record = build_audit_record(case, review)
    record["provider_fields"] = crossed_boundary

    return CapstoneResult(
        review=review, audit=record, escalated=escalate, escalation_reason=reason)
