"""Ports share the v4.1 slice: same tools, same veto, same golden set."""

from __future__ import annotations

import json
from pathlib import Path

from medguard.eval.scoring import score_structured
from medguard.pipeline import review_case
from medguard.types import APPROVE, ESCALATE, FLAG
from ports.adk.agent import review as adk_review
from ports.agno.agent import review as agno_review
from ports.anthropic.adapter import AnthropicAdapter
from ports.langgraph.graph import medguard_core_node, review as lg_review
from ports.openai.adapter import OpenAIAdapter
from ports.slice import apply_independent_veto, review_v41, run_medguard_core

_ROOT = Path(__file__).resolve().parents[1]
_GOLDEN = _ROOT / "evals" / "golden_set.json"

_SAFE = {
    "patient": {"age": 55, "egfr_ml_min": 90, "conditions": ["hypertension"]},
    "current_medications": [],
    "proposed": {"drug": "amlodipine", "dose": "5 mg", "frequency": "once daily"},
}
_GABA = {
    "patient": {"age": 82, "egfr_ml_min": 22, "conditions": ["chronic kidney disease stage 4"]},
    "current_medications": [{"drug": "metformin", "dose": "500 mg", "frequency": "twice daily"}],
    "proposed": {"drug": "gabapentin", "dose": "600 mg", "frequency": "three times daily"},
}
_WARFARIN = {
    "patient": {"age": 60, "egfr_ml_min": 88, "conditions": ["atrial fibrillation"]},
    "current_medications": [{"drug": "warfarin", "dose": "5 mg", "frequency": "once daily"}],
    "proposed": {"drug": "ciprofloxacin", "dose": "500 mg", "frequency": "twice daily"},
}


def test_slice_matches_canonical_v41():
    for case in (_SAFE, _GABA, _WARFARIN):
        assert review_v41(case).verdict == review_case(case, guardrails=True).verdict


def test_core_without_veto_still_misses_renal_overdose():
    assert run_medguard_core(_GABA).verdict == APPROVE
    assert apply_independent_veto(run_medguard_core(_GABA), _GABA).verdict == ESCALATE


def test_wrappers_share_the_same_slice():
    assert lg_review(_GABA).verdict == ESCALATE
    assert adk_review(_GABA).verdict == ESCALATE
    assert agno_review(_GABA).verdict == ESCALATE
    assert lg_review(_SAFE).verdict == APPROVE
    assert lg_review(_WARFARIN).verdict == FLAG


def test_graph_core_node_does_not_veto():
    out = medguard_core_node({"case": _GABA})
    assert out["core_review"].verdict == APPROVE


def test_adapters_are_complete_callables():
    assert callable(OpenAIAdapter(api_key="sk-test").complete)
    assert callable(AnthropicAdapter(api_key="sk-test").complete)


def test_port_slice_golden_set_zero_unsafe():
    data = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    report = score_structured(data["cases"], review_v41)
    assert report.passed
    assert report.unsafe_approvals == []
