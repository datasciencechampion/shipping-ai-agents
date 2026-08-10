"""Tests for v3.2 tool hardening: validation, timeout, safe retries, explicit errors."""

import pytest

from medguard.pipeline import review_case
from medguard.tools import (
    DEFAULT_TIMEOUT_S,
    ToolError,
    TransientToolError,
    call_reliably,
    check_interactions,
)
from medguard.types import ESCALATE


def test_validation_rejects_missing_drug():
    with pytest.raises(ToolError):
        check_interactions([], {"dose": "5 mg"})  # no 'drug'


def test_validation_rejects_wrong_types():
    with pytest.raises(ToolError):
        check_interactions("not-a-list", {"drug": "amlodipine"})


def test_call_reliably_returns_result_on_success():
    out = call_reliably(check_interactions, [], {"drug": "amlodipine"})
    assert out == []


def test_call_reliably_retries_transient_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientToolError("blip")
        return "ok"

    assert call_reliably(flaky, retries=2) == "ok"
    assert calls["n"] == 2


def test_call_reliably_does_not_retry_non_idempotent():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        raise TransientToolError("blip")

    with pytest.raises(TransientToolError):
        call_reliably(flaky, retries=3, idempotent=False)
    assert calls["n"] == 1  # a non-idempotent call is tried exactly once


def test_call_reliably_wraps_unknown_error_as_toolerror():
    def boom():
        raise ValueError("kaboom")

    with pytest.raises(ToolError):
        call_reliably(boom)


def test_timeout_becomes_transient_error():
    import time

    def slow():
        time.sleep(0.2)
        return "late"

    with pytest.raises(ToolError):
        call_reliably(slow, timeout_s=0.01, retries=0)


def test_pipeline_escalates_when_interaction_tool_fails(monkeypatch):
    # A tool failure must escalate, never approve (the Chapter 9 post-mortem).
    import medguard.pipeline as pipe

    def broken(current, proposed):
        raise ToolError("interaction DB unavailable")

    monkeypatch.setattr(pipe, "check_interactions", broken)
    case = {
        "patient": {"age": 55, "egfr_ml_min": 90, "conditions": []},
        "current_medications": [{"drug": "warfarin"}],
        "proposed": {"drug": "ciprofloxacin", "dose": "500 mg", "frequency": "twice daily"},
    }
    assert review_case(case).verdict == ESCALATE


def test_default_timeout_is_sane():
    assert DEFAULT_TIMEOUT_S > 0
