"""Grounding and citation verification for MedGuard (v3.1).

A finding is only trustworthy if it points at a real source (Chapter 8). This
module holds a small source store and verifies that every citation a finding
carries actually resolves to a known source. A finding whose citation cannot be
resolved is *unverified*: we do not silently keep it, and we do not silently drop
its safety signal either. Unverified findings force the review to abstain
(escalate) rather than approve on the strength of a possibly hallucinated cite.
"""

from __future__ import annotations

from .types import Finding

# The corpus MedGuard is allowed to cite. In a deployment this is a retrieval
# index over an approved formulary; here it is a small, explicit allow-list so
# citation verification is deterministic and testable offline.
_SOURCES: dict[str, str] = {
    "BNF: warfarin — interactions":
        "Warfarin: anticoagulant effect enhanced by ciprofloxacin; monitor INR.",
    "BNF: methotrexate — interactions":
        "Methotrexate: trimethoprim increases risk of haematological toxicity.",
    "Input guardrail":
        "MedGuard input-guardrail policy (not a clinical source).",
    "Independent dose-ceiling guardrail":
        "MedGuard renal-adjusted dose-ceiling policy (not a clinical source).",
}


def is_grounded(citation: str | None) -> bool:
    """True if the citation resolves to a known source."""
    return bool(citation) and citation in _SOURCES


def source_text(citation: str) -> str | None:
    """Return the cited source snippet, or None if the citation is unknown."""
    return _SOURCES.get(citation)


def verify_findings(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """Split findings into (verified, unverified).

    A finding with no citation at all is treated as unverified: a clinical claim
    without a source is exactly what we refuse to trust.
    """
    verified: list[Finding] = []
    unverified: list[Finding] = []
    for f in findings:
        (verified if is_grounded(f.citation) else unverified).append(f)
    return verified, unverified
