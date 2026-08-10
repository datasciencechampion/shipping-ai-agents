"""Tests for v4.3 auditable, isolated data flows."""

from medguard.audit import (
    AuditLog,
    build_audit_record,
    provider_payload,
    scan_for_phi,
)
from medguard.types import FLAG, Finding, Review

_CASE = {
    "patient": {
        "name": "Jane Roe", "mrn": "MRN-99887", "dob": "1950-02-03",
        "age": 76, "egfr_ml_min": 40, "conditions": ["ckd stage 3"],
    },
    "current_medications": [{"drug": "warfarin", "dose": "5 mg"}],
    "proposed": {"drug": "ciprofloxacin", "dose": "500 mg", "frequency": "twice daily"},
}
_IDENTIFIERS = {"Jane Roe", "MRN-99887", "1950-02-03"}


def test_provider_payload_strips_direct_identifiers():
    payload = provider_payload(_CASE)
    p = payload["patient"]
    assert "name" not in p and "mrn" not in p and "dob" not in p
    # Clinical fields the model needs are retained.
    assert p["age"] == 76 and p["egfr_ml_min"] == 40
    assert scan_for_phi(payload, _IDENTIFIERS) == []


def test_scan_for_phi_detects_leak():
    leaked = scan_for_phi({"note": "patient Jane Roe, MRN-99887"}, _IDENTIFIERS)
    assert leaked == ["Jane Roe", "MRN-99887"]  # sorted; dob was not present


def test_audit_record_redacts_identity_but_keeps_decision():
    review = Review(FLAG, [Finding("interaction", "moderate", "cipro+warfarin",
                                   "BNF: warfarin — interactions", source="tool")],
                    0.9, "trace-abc")
    rec = build_audit_record(_CASE, review, actor="pharmacist:kp")
    assert rec["verdict"] == FLAG
    assert rec["trace_id"] == "trace-abc"
    assert rec["findings"][0]["citation"] == "BNF: warfarin — interactions"
    # Identity is redacted in the record.
    assert scan_for_phi(rec, _IDENTIFIERS) == []


def test_audit_log_assert_clean_passes_and_fails():
    review = Review(FLAG, [], 0.9, "t1")
    log = AuditLog()
    log.record(_CASE, review)
    log.assert_clean(_IDENTIFIERS)  # redacted record is clean

    # A case that smuggles an identifier into a non-redacted field must be caught.
    leaky_case = dict(_CASE, proposed={"drug": "aspirin", "note": "ref Jane Roe"})
    log.record(leaky_case, review)
    try:
        log.assert_clean(_IDENTIFIERS)
    except AssertionError as exc:
        assert "Jane Roe" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected assert_clean to detect the leak")
