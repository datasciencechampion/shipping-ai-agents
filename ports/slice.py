"""One v4.1 slice shared by every port: MedGuard core, then an independent veto.

The model (or a framework graph) must not own the dose-ceiling check. Call
``run_medguard_core`` (tools + structured decide, no veto), then
``apply_independent_veto``. ``review_v41`` does both, in that order.
"""

from __future__ import annotations

from medguard.guardrails import apply_dose_ceiling
from medguard.pipeline import review_case
from medguard.types import Review


def run_medguard_core(case: dict) -> Review:
    """Canonical tools, grounding, and decide. Guardrails off on purpose."""
    return review_case(case, guardrails=False)


def apply_independent_veto(review: Review, case: dict) -> Review:
    """Chapter 12: ordinary code after the reasoner, not inside it."""
    return apply_dose_ceiling(review, case)


def review_v41(case: dict) -> Review:
    """Same safety property as ``medguard-eval --agent v41``."""
    return apply_independent_veto(run_medguard_core(case), case)
