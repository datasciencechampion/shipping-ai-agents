"""Agno port: the agent calls MedGuard; the veto is not an LLM instruction.

Install (optional, live demos): ``pip install agno``

``review()`` is the offline slice. ``build_agent()`` needs a model id and the
Agno package. After ``agent.run``, apply ``apply_independent_veto`` in Python.
"""

from __future__ import annotations

from ports.slice import apply_independent_veto, run_medguard_core
from medguard.types import Review


def review(case: dict) -> Review:
    inner = run_medguard_core(case)
    return apply_independent_veto(inner, case)


def medguard_core_tool(case: dict) -> dict:
    return run_medguard_core(case).to_dict()


def build_agent(*, model=None):
    try:
        from agno.agent import Agent
    except ImportError as exc:
        raise RuntimeError("Install Agno: pip install agno") from exc

    kwargs = {
        "name": "MedGuard",
        "tools": [medguard_core_tool],
        "instructions": (
            "Call medguard_core_tool with the case. Do not invent a dose ceiling."
        ),
    }
    if model is not None:
        kwargs["model"] = model
    return Agent(**kwargs)
