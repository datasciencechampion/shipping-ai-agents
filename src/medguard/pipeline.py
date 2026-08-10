"""MedGuard v3+ review pipeline: a bounded state machine with a structured verdict.

This replaces v0's single opaque call (Chapter 7). The review walks a fixed,
inspectable sequence of states, emitting a trace span (Chapter 5) per state, under
a hard step budget with a guaranteed terminal state. The decide state returns a
structured `Review` — no prose, so no brittle extractor.

Optionally applies the independent output guardrails of v4.1 (Chapter 12).
"""

from __future__ import annotations

from .budget import Budget, BudgetTracker
from .grounding import verify_findings
from .guardrails import apply_dose_ceiling, scan_for_injection
from .ops import BehaviorBundle, KillSwitch
from .tools import (
    ToolError,
    call_reliably,
    check_contraindications,
    check_interactions,
)
from .trace import Trace
from .types import APPROVE, ESCALATE, FLAG, Finding, Review

# Ordered states of the review. The step budget must be >= len(STATES).
STATES = ("gather", "check_interactions", "check_contraindications", "check_dose", "decide")


def _decide(findings: list[Finding]) -> tuple[str, float]:
    """Map findings to a verdict + confidence. High -> escalate; any other -> flag."""
    if not findings:
        return APPROVE, 0.9
    if any(f.severity == "high" for f in findings):
        return ESCALATE, 0.95
    return FLAG, 0.9


def review_case(
    case: dict,
    *,
    guardrails: bool = True,
    step_budget: int = 8,
    trace: Trace | None = None,
    kill_switch: KillSwitch | None = None,
    verify_citations: bool = True,
    min_confidence: float = 0.0,
    bundle: BehaviorBundle | None = None,
    budget: Budget | None = None,
) -> Review:
    """Run one structured review. `guardrails=False` gives the pre-v4.1 behavior.

    v2.1: an engaged `kill_switch` degrades straight to human review.
    v3.1: `verify_citations` forces escalation on any ungrounded finding.
    v4:   `min_confidence` routes low-confidence decisions to a human.
    v4.2: an exceeded `budget` (cost or latency) routes to a human.
    """
    trace = trace or Trace()
    patient = case.get("patient", {})
    proposed = case.get("proposed", {})
    current = case.get("current_medications", [])
    findings: list[Finding] = []
    steps = 0
    tracker = BudgetTracker(budget) if budget is not None else None
    model = bundle.model if bundle is not None else "gpt-4o-mini"

    with trace.span("review", verdict_pending=True) as root:
        if bundle is not None:
            root.set(bundle_version=bundle.version)
        # v2.1: kill switch degrades to human review, never to an error.
        if kill_switch is not None and kill_switch.engaged:
            root.set(verdict_pending=False, verdict=ESCALATE,
                     kill_switch=kill_switch.reason or "engaged")
            return Review(ESCALATE, findings, 0.5, trace.trace_id)
        for state in STATES:
            steps += 1
            if steps > step_budget:  # termination guard (Chapter 7)
                root.set(terminated="step_budget_exceeded")
                return Review(ESCALATE, findings, 0.5, trace.trace_id)

            with trace.span(state) as span:
                if state == "gather":
                    # Input guardrail: never obey instructions embedded in data.
                    note = str(patient.get("note", "")) + str(proposed.get("note", ""))
                    if guardrails and note and scan_for_injection(note):
                        span.set(injection_detected=True)
                        findings.append(Finding(
                            "contraindication", "high",
                            "Instruction-injection detected in record text; treated as data.",
                            "Input guardrail", source="guardrail"))
                elif state == "check_interactions":
                    try:
                        # v3.2: run under a timeout with safe retries; a failure
                        # raises ToolError rather than returning an empty result.
                        found = call_reliably(check_interactions, current, proposed)
                    except ToolError as exc:  # a tool error is NOT 'all clear'
                        span.status = "error"
                        span.set(error=str(exc))
                        return Review(ESCALATE, findings, 0.5, trace.trace_id)
                    span.set(found=len(found))
                    findings.extend(found)
                    if tracker is not None:  # nominal model-call cost for the review
                        cost = tracker.record(model, tokens_in=800, tokens_out=200)
                        span.set(model=model, cost_usd=cost)
                elif state == "check_contraindications":
                    findings.extend(check_contraindications(patient, proposed))
                elif state == "check_dose":
                    # v3's reasoner has no renal dose model; v4.1's guardrail covers it.
                    span.set(note="dose safety delegated to output guardrail")
                elif state == "decide":
                    # v3.1: a finding we cannot ground is not evidence we can act
                    # on — abstain to a human rather than trust a possible cite.
                    if verify_citations:
                        _, unverified = verify_findings(findings)
                        span.set(unverified=len(unverified))
                    else:
                        unverified = []
                    verdict, confidence = _decide(findings)
                    if unverified:
                        verdict, confidence = ESCALATE, min(confidence, 0.5)
                    review = Review(verdict, list(findings), confidence, trace.trace_id)
                    if guardrails:
                        review = apply_dose_ceiling(review, case)
                    # v4: low decision confidence routes to a human.
                    if review.verdict != ESCALATE and review.confidence < min_confidence:
                        span.set(routed="low_confidence")
                        review = Review(ESCALATE, review.findings,
                                        review.confidence, trace.trace_id)
                    # v4.2: a blown cost/latency budget also routes to a human.
                    if tracker is not None:
                        root.set(cost_usd=tracker.spent_usd, budget_status=tracker.status())
                        if review.verdict != ESCALATE and tracker.over_budget():
                            span.set(routed=f"budget_{tracker.status()}")
                            review = Review(ESCALATE, review.findings,
                                            review.confidence, trace.trace_id)
                    root.set(verdict_pending=False, verdict=review.verdict,
                             max_severity=review.max_severity())
                    return review

    # Unreachable: decide always returns. Terminal safety net.
    return Review(ESCALATE, findings, 0.5, trace.trace_id)
