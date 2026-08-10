"""MedGuard v0 — the naive single-call agent.

Given a case (patient + current medications + a proposed prescription), build one
prompt, make one model call, and return the prose. That's the whole agent.

Everything that would make this *safe* — evaluation, grounding, a dose
calculator, guardrails, escalation, tracing — is deliberately missing at v0.
"""

from __future__ import annotations

import json
from typing import Any

from .config import Config
from .model import call_model

_SYSTEM_PREAMBLE = (
    "You are a clinical pharmacology assistant. Given a patient, their current "
    "medications, and a proposed new prescription, assess whether the proposed "
    "prescription is safe. Consider drug-drug interactions, contraindications, "
    "and dosing."
)


def build_prompt(case: dict[str, Any]) -> str:
    """Render a case into the single prompt v0 sends to the model."""
    patient = json.dumps(case.get("patient", {}), indent=2)
    current = json.dumps(case.get("current_medications", []), indent=2)
    proposed = json.dumps(case.get("proposed", {}), indent=2)
    return (
        f"{_SYSTEM_PREAMBLE}\n\n"
        f"PATIENT:\n{patient}\n\n"
        f"CURRENT MEDICATIONS:\n{current}\n\n"
        f"PROPOSED PRESCRIPTION:\n{proposed}\n\n"
        "Give your assessment."
    )


def review(case: dict[str, Any], config: Config | None = None) -> str:
    """Run a v0 review and return the model's free-text assessment."""
    config = config or Config.from_env()
    prompt = build_prompt(case)
    return call_model(prompt, config, context=case)
