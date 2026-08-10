"""Extract a structured verdict from v0's free-text output.

v0 answers in prose, but scoring needs a decision: APPROVE, FLAG, or ESCALATE.
This extractor is a *deliberate stopgap*. Keyword matching over natural language
is brittle — negations like "no significant interaction" routinely fool it — and
that fragility is itself a lesson: it's a symptom of an agent that emits prose
instead of structured output. Chapter 3 discusses replacing it with structured
outputs and an LLM-judge; Chapter 7 removes the need entirely by having the agent
return a structured verdict directly.
"""

from __future__ import annotations

APPROVE = "APPROVE"
FLAG = "FLAG"
ESCALATE = "ESCALATE"

# Strong phrases are checked first because they express an overall judgment that
# should override incidental keywords elsewhere in the prose.
_STRONG_ESCALATE = ("consult a pharmacist", "refer to a specialist", "unable to determine", "seek specialist")
_STRONG_APPROVE = ("safe to prescribe", "safe to give", "no contraindication")

_FLAG_MARKERS = (
    "contraindicated", "avoid", "do not prescribe", "not recommended",
    "reduce the dose", "lower the dose", "dose reduction", "adjust the dose",
    "significant interaction", "increased risk", "bleeding risk", "caution",
    "monitor closely", "toxicity",
)
_APPROVE_MARKERS = (
    "looks appropriate", "is appropriate", "well tolerated",
    "start the patient", "start at this dose", "no significant interaction",
)


def extract_verdict(text: str) -> str:
    """Map free-text advice to APPROVE / FLAG / ESCALATE (best effort)."""
    t = text.lower()

    if any(p in t for p in _STRONG_ESCALATE):
        return ESCALATE
    if any(p in t for p in _STRONG_APPROVE):
        return APPROVE

    has_flag = any(p in t for p in _FLAG_MARKERS)
    has_approve = any(p in t for p in _APPROVE_MARKERS)

    if has_flag:
        return FLAG  # any explicit concern outweighs a soft approval
    if has_approve:
        return APPROVE
    return ESCALATE  # unknown -> escalate is the safer default
