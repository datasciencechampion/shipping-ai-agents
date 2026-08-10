"""Tests for the v2 tracing layer: span tree, timing, PHI redaction, error status."""

import pytest

from medguard.trace import Trace, cost_usd, redact


def test_span_tree_nests_and_times():
    t = Trace(trace_id="fixed")
    with t.span("review"):
        with t.span("model_call") as m:
            m.set(tokens_in=10, tokens_out=5)
    assert t.trace_id == "fixed"
    assert t.root.name == "review"
    assert len(t.root.children) == 1
    child = t.root.children[0]
    assert child.name == "model_call"
    assert child.attributes["tokens_in"] == 10
    assert t.root.duration_ms is not None and t.root.duration_ms >= 0


def test_redact_masks_phi_by_field_name():
    out = redact({"patient": {"age": 82}, "drug": "gabapentin", "note": "secret"})
    assert out["patient"] == "***REDACTED***"   # whole PHI field masked
    assert out["note"] == "***REDACTED***"
    assert out["drug"] == "gabapentin"           # non-PHI preserved


def test_span_set_redacts_at_boundary():
    t = Trace()
    with t.span("gather") as s:
        s.set(patient={"age": 82, "conditions": ["ckd"]})
    assert t.root.attributes["patient"] == "***REDACTED***"


def test_error_status_recorded():
    t = Trace()
    with pytest.raises(ValueError):
        with t.span("boom"):
            raise ValueError("kaboom")
    assert t.root.status == "error"


def test_to_dict_is_serializable_shape():
    t = Trace(trace_id="x")
    with t.span("review"):
        pass
    d = t.to_dict()
    assert d["trace_id"] == "x"
    assert d["root"]["name"] == "review"


def test_cost_usd():
    assert cost_usd(1000, 1000, in_rate=0.5, out_rate=1.5) == 2.0
