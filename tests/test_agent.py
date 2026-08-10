"""Tests for the deterministic parts of the agent: prompt building and the
fake-mode review path. The model itself is non-deterministic, so we pin down
everything around it."""

from medguard.agent import build_prompt, review
from medguard.config import Config

_CASE = {
    "case_id": "t",
    "patient": {"age": 82, "conditions": ["chronic kidney disease stage 4"]},
    "current_medications": [{"drug": "metformin", "dose": "500 mg"}],
    "proposed": {"drug": "gabapentin", "dose": "600 mg"},
}


def test_build_prompt_is_deterministic():
    assert build_prompt(_CASE) == build_prompt(_CASE)


def test_build_prompt_contains_all_sections():
    prompt = build_prompt(_CASE)
    assert "PATIENT:" in prompt
    assert "CURRENT MEDICATIONS:" in prompt
    assert "PROPOSED PRESCRIPTION:" in prompt
    assert "gabapentin" in prompt


def test_fake_review_is_deterministic():
    cfg = Config(fake=True)
    assert review(_CASE, cfg) == review(_CASE, cfg)


def test_fake_review_mentions_proposed_drug_and_dose():
    out = review(_CASE, Config(fake=True))
    assert "gabapentin" in out
    assert "600 mg" in out
