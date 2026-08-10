"""Tests for v2.1 operational controls: bundle registry, rollback, kill switch."""

from medguard.ops import BehaviorBundle, BundleRegistry, KillSwitch
from medguard.pipeline import review_case
from medguard.types import APPROVE, ESCALATE

_SAFE = {
    "patient": {"age": 55, "egfr_ml_min": 90, "conditions": ["hypertension"]},
    "current_medications": [],
    "proposed": {"drug": "amlodipine", "dose": "5 mg", "frequency": "once daily"},
}


def test_registry_rollback_returns_previous_bundle():
    v1 = BehaviorBundle("2026.01.0")
    v2 = BehaviorBundle("2026.02.0", prompt_version="v1")
    reg = BundleRegistry(v1)
    reg.deploy(v2)
    assert reg.current == v2
    assert reg.rollback() == v1
    # Rolling back past the origin is a safe no-op.
    assert reg.rollback() == v1


def test_engaged_kill_switch_degrades_to_human():
    ks = KillSwitch()
    ks.engage("interaction table under investigation")
    r = review_case(_SAFE, kill_switch=ks)
    assert r.verdict == ESCALATE  # degrade to human, not to an error


def test_disengaged_kill_switch_is_transparent():
    ks = KillSwitch()  # default: not engaged
    assert review_case(_SAFE, kill_switch=ks).verdict == APPROVE


def test_bundle_version_recorded_on_trace():
    from medguard.trace import Trace
    tr = Trace()
    review_case(_SAFE, trace=tr, bundle=BehaviorBundle("2026.02.0"))
    assert tr.root is not None
    assert tr.root.attributes.get("bundle_version") == "2026.02.0"
