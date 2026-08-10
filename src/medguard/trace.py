"""Structured tracing for MedGuard (v2).

A trace is the complete, structured record of one review: a tree of spans, each
capturing a unit of work (the review, a model call, a tool call, a guardrail
check) with timing, status, and attributes. Traces are structured data, not prose
logs, so they can be queried, aggregated, and — decisively — replayed.

PHI never enters a span raw: attributes pass through `redact()` at the boundary,
so sensitive fields are masked before anything is recorded (Chapter 14).
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

# Field names that must never be recorded in the clear. Kept deliberately small
# and explicit; a real system would centralize this policy (Chapter 14).
PHI_FIELDS = frozenset({"patient", "name", "dob", "mrn", "conditions", "note", "notes"})
_REDACTED = "***REDACTED***"


def redact(value: Any, _key: str | None = None) -> Any:
    """Recursively mask PHI fields by name. Structure is preserved; values aren't."""
    if _key is not None and _key.lower() in PHI_FIELDS:
        return _REDACTED
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


@dataclass
class Span:
    name: str
    start: float
    end: float | None = None
    status: str = "ok"  # ok | error | timeout
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list["Span"] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        return None if self.end is None else round((self.end - self.start) * 1000, 3)

    def set(self, **attrs: Any) -> None:
        """Record attributes, redacting PHI at the boundary."""
        for key, val in attrs.items():
            self.attributes[key] = redact(val, key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "children": [c.to_dict() for c in self.children],
        }


class Trace:
    """Builds a span tree for one request, identified by a stable trace_id."""

    def __init__(self, trace_id: str | None = None, clock=time.perf_counter):
        self.trace_id = trace_id or uuid.uuid4().hex
        self._clock = clock
        self._stack: list[Span] = []
        self.root: Span | None = None

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[Span]:
        span = Span(name=name, start=self._clock())
        span.set(**attrs)
        if self._stack:
            self._stack[-1].children.append(span)
        else:
            self.root = span
        self._stack.append(span)
        try:
            yield span
        except Exception:
            span.status = "error"
            raise
        finally:
            span.end = self._clock()
            self._stack.pop()

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "root": self.root.to_dict() if self.root else None}


def cost_usd(tokens_in: int, tokens_out: int, *, in_rate: float, out_rate: float) -> float:
    """Cost from token counts. Rates are USD per 1K tokens (Chapter 13 uses this)."""
    return round((tokens_in * in_rate + tokens_out * out_rate) / 1000, 6)
