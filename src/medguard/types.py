"""Structured result types for MedGuard (v3+).

From v3 on, the agent returns a structured `Review` instead of prose. This is the
change that retires the brittle verdict extractor of Chapters 3-4: there's no
prose to parse because the decision is structured at the source.
"""

from __future__ import annotations

from dataclasses import dataclass, field

APPROVE = "APPROVE"
FLAG = "FLAG"
ESCALATE = "ESCALATE"

SEVERITIES = ("none", "low", "moderate", "high")
_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass(frozen=True)
class Finding:
    type: str            # interaction | contraindication | dosing
    severity: str        # one of SEVERITIES
    explanation: str
    citation: str | None = None
    source: str = "model"  # "model"/"tool" vs "guardrail" — who raised it


@dataclass
class Review:
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    confidence: float = 0.0
    trace_id: str | None = None

    def max_severity(self) -> str:
        if not self.findings:
            return "none"
        return max((f.severity for f in self.findings), key=lambda s: _SEVERITY_RANK[s])

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "max_severity": self.max_severity(),
            "trace_id": self.trace_id,
            "findings": [vars(f) for f in self.findings],
        }
