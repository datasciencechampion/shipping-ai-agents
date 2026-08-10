"""Auditable, isolated data flows for MedGuard (v4.3).

Two obligations from Chapter 14, honored in code:

1. *Data boundaries.* Direct identifiers never leave the boundary. `provider_payload`
   returns only what the model needs to reason clinically, with identifiers stripped
   at the edge — the data-flow map is enforced, not just documented.

2. *A compliance-grade audit trail.* `build_audit_record` turns a review + its trace
   into an append-only record that proves what was decided, with PHI redacted at the
   boundary (reusing the Chapter 5 redaction). `scan_for_phi` is the tripwire that
   catches the "PHI in a debug log" failure: any log or record can be asserted clean.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .trace import redact
from .types import Review

# Direct identifiers that must never cross the boundary to a model provider or a
# log. Clinical fields (age, egfr, conditions) may flow because the model needs
# them to reason; identity does not.
DIRECT_IDENTIFIERS = frozenset({"name", "mrn", "dob", "ssn", "address", "phone", "email"})


def provider_payload(case: dict) -> dict:
    """The subset of a case allowed to leave for the model provider.

    Direct identifiers are removed at the boundary; clinical fields remain.
    """
    patient = {
        k: v for k, v in case.get("patient", {}).items()
        if k.lower() not in DIRECT_IDENTIFIERS
    }
    return {
        "patient": patient,
        "current_medications": case.get("current_medications", []),
        "proposed": case.get("proposed", {}),
    }


def scan_for_phi(obj: Any, identifiers: set[str]) -> list[str]:
    """Return any identifier values that appear anywhere in `obj` (serialized).

    Used as a tripwire: an audit record or log line must scan clean before it's
    accepted. A privacy boundary with a convenient bypass is not a boundary.
    """
    blob = str(obj)
    return sorted({v for v in identifiers if v and v in blob})


def build_audit_record(case: dict, review: Review, *, actor: str = "medguard") -> dict:
    """Build a redacted, append-only audit record proving what was decided."""
    return {
        "trace_id": review.trace_id,
        "at": time.time(),
        "actor": actor,
        "verdict": review.verdict,
        "max_severity": review.max_severity(),
        # Enough to reconstruct the reasoning; identity redacted at the boundary.
        "patient": redact(case.get("patient", {})),
        "proposed": case.get("proposed", {}),
        "findings": [
            {"type": f.type, "severity": f.severity,
             "explanation": f.explanation, "citation": f.citation}
            for f in review.findings
        ],
    }


@dataclass
class AuditLog:
    """An append-only audit trail with a built-in PHI tripwire."""
    _records: list[dict] = field(default_factory=list)

    def record(self, case: dict, review: Review, *, actor: str = "medguard") -> dict:
        rec = build_audit_record(case, review, actor=actor)
        self._records.append(rec)
        return rec

    def __len__(self) -> int:
        return len(self._records)

    def assert_clean(self, identifiers: set[str]) -> None:
        """Raise if any direct identifier leaked into the trail."""
        for rec in self._records:
            leaked = scan_for_phi(rec, identifiers)
            if leaked:
                raise AssertionError(f"PHI leaked into audit log: {leaked}")
