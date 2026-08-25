"""Google ADK port: the agent calls MedGuard; the veto is not an LLM instruction.

Install (optional, live demos): ``pip install google-adk``

``review()`` is the offline slice. ``build_agent()`` wires ADK when the package
is present; APIs move quickly, so treat ``build_agent`` as indicative and keep
the veto in ``review()`` / after ``run_medguard_core``.
"""

from __future__ import annotations

from ports.slice import apply_independent_veto, run_medguard_core
from medguard.types import Review


def review(case: dict) -> Review:
    inner = run_medguard_core(case)
    return apply_independent_veto(inner, case)


def medguard_core_tool(case: dict) -> dict:
    """Tool the ADK agent can call. Returns a dict; no veto."""
    return run_medguard_core(case).to_dict()


def build_agent():
    """Construct an ADK agent that uses MedGuard as a tool.

    After the agent returns, apply ``apply_independent_veto`` in your runner.
    Do not ask the model to police the dose ceiling.
    """
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError(
            "Install Google ADK: pip install google-adk"
        ) from exc

    return Agent(
        name="medguard",
        description="Medication-safety review. Tools run MedGuard core; veto is outside.",
        tools=[medguard_core_tool],
    )
